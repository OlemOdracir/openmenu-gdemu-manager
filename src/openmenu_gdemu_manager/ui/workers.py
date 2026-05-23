import logging
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal

from .. import REPOSITORY_URL

from ..core.image_quality import analyze_image, save_cover_set
from ..core.matching import safe_filename
from ..core.models import BulkProposal, GameItem, RomLibraryEntry
from ..core.placeholder import ensure_no_cover_asset
from ..config.paths import INBOX_NORMALIZED_DIR, INBOX_ORIGINALS_DIR, INBOX_PREVIEW_DIR, STATE_PATH
from ..dreamcast.scanner import scan_sd_root
from ..covers.search import best_auto_candidate, find_candidates, load_candidate_image
from ..covers.providers.base import read_json_url
from ..covers.providers.registry import provider_threshold, source_provider_id
from ..config.settings import load_settings
from ..dreamcast.metadata import find_openmenu_track, parse_openmenu_from_track
from ..dreamcast.sd_writer import (
    write_name_txt,
    write_openmenu_ini,
)
from ..config.state import drop_game_state, flush_state, patch_game_state
from ..dreamcast.storage_diagnostics import diagnose_storage
from ..services.cover_service import persist_cover_selection
from ..services.cover_library import count_new_candidates, load_saved_candidates
from ..services.game_service import build_pending_game, next_free_slot
from ..services.legacy_menu_upgrade import LegacyMenuUpgradeService
from ..services.openmenu_rebuilder import OpenMenuRebuilder
from ..services.search_log import append_search_event_for_game, summarize_candidates
from ..services.sd_slot_transaction import SdSlotTransactionService
from ..services.transaction_log import append_transaction, new_operation_id

log = logging.getLogger(__name__)
GITHUB_LATEST_RELEASE_API = "https://api.github.com/repos/OlemOdracir/openmenu-gdemu-manager/releases/latest"


def start_worker(worker: QObject, thread_attr: str, worker_attr: str, owner,
                 on_finished, on_error, extra: list | None = None) -> None:
    thread = QThread()
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.finished.connect(on_finished)
    worker.error.connect(on_error)
    if extra:
        for signal, slot in extra:
            signal.connect(slot)
    worker.finished.connect(thread.quit)
    worker.error.connect(thread.quit)
    worker.finished.connect(worker.deleteLater)
    worker.error.connect(worker.deleteLater)
    thread.finished.connect(lambda: setattr(owner, worker_attr, None))
    thread.finished.connect(lambda: setattr(owner, thread_attr, None))
    thread.finished.connect(thread.deleteLater)
    setattr(owner, thread_attr, thread)
    setattr(owner, worker_attr, worker)
    thread.start()


class ScanWorker(QObject):
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, root: Path, state: dict):
        super().__init__()
        self.root = root
        self.state = state

    def run(self):
        try:
            log.info("ScanWorker started: %s", self.root)
            self.finished.emit(scan_sd_root(self.root, self.state))
        except Exception as exc:
            log.exception("ScanWorker failed")
            self.error.emit(str(exc))


class DiagnosticWorker(QObject):
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, root: Path):
        super().__init__()
        self.root = root

    def run(self):
        try:
            log.info("DiagnosticWorker started: %s", self.root)
            self.finished.emit(diagnose_storage(self.root))
        except Exception as exc:
            log.exception("DiagnosticWorker failed")
            self.error.emit(str(exc))


class LegacyMenuUpgradeWorker(QObject):
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, root: Path):
        super().__init__()
        self.root = Path(root)

    def run(self):
        try:
            log.info("LegacyMenuUpgradeWorker started: %s", self.root)
            self.finished.emit(LegacyMenuUpgradeService().upgrade(self.root))
        except Exception as exc:
            log.exception("Legacy menu upgrade failed")
            self.error.emit(str(exc))


class UpdateCheckWorker(QObject):
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, current_version: str):
        super().__init__()
        self.current_version = current_version

    def run(self):
        try:
            payload = read_json_url(GITHUB_LATEST_RELEASE_API, timeout=6)
            latest = str(payload.get("tag_name") or payload.get("name") or "").lstrip("vV")
            if not latest:
                self.finished.emit({"ok": False, "reason": "no_release"})
                return
            self.finished.emit({
                "ok": True,
                "current": self.current_version,
                "latest": latest,
                "url": str(payload.get("html_url") or REPOSITORY_URL),
                "newer": _version_tuple(latest) > _version_tuple(self.current_version),
            })
        except Exception as exc:
            log.exception("Update check failed")
            self.error.emit(str(exc))


def _version_tuple(value: str) -> tuple[int, ...]:
    parts: list[int] = []
    for raw in str(value).replace("-", ".").split("."):
        digits = "".join(ch for ch in raw if ch.isdigit())
        if digits:
            parts.append(int(digits))
    return tuple(parts or [0])


def _save_transaction_summary(
    root_path: Path,
    additions: list[GameItem],
    deletions: list[GameItem],
    renamed: list[GameItem],
    covers: list[GameItem],
    product_updates: list[GameItem],
    slot_moves: list[dict],
    before_metadata: dict[int, dict[str, str]],
) -> dict:
    changes: list[dict] = []
    for game in additions:
        changes.append({
            "type": "game_added",
            "slot": game.slot,
            "name": game.name,
            "product_id": game.product_id,
            "source_path": str(game.source_path or ""),
        })
    for game in deletions:
        old_data = before_metadata.get(game.slot, {})
        changes.append({
            "type": "game_removed",
            "slot": game.slot,
            "name": old_data.get("name") or game.name,
            "product_id": old_data.get("product_id") or game.product_id,
            "folder": str(game.folder or ""),
        })
    for game in renamed:
        old_data = before_metadata.get(game.slot, {})
        old_name = old_data.get("name") or ""
        if old_name and old_name != game.name:
            changes.append({
                "type": "name_changed",
                "slot": game.slot,
                "old_name": old_name,
                "new_name": game.name,
                "product_id": game.product_id,
            })
    for game in covers:
        changes.append({
            "type": "cover_changed",
            "slot": game.slot,
            "name": game.name,
            "product_id": game.product_id,
            "image_path": str(game.selected_image or ""),
            "source": game.selected_source,
        })
    for game in product_updates:
        old_data = before_metadata.get(game.slot, {})
        old_product = old_data.get("product") or ""
        if old_product and old_product != game.product_id:
            changes.append({
                "type": "product_id_changed",
                "slot": game.slot,
                "name": game.name,
                "old_product_id": old_product,
                "new_product_id": game.product_id,
                "artwork_aliases": list(game.artwork_serials),
            })
    for move in slot_moves:
        changes.append({
            "type": "slot_compacted",
            **move,
        })
    return {
        "root": str(Path(root_path).resolve()),
        "summary": {
            "added": len(additions),
            "removed": len(deletions),
            "renamed": len([change for change in changes if change["type"] == "name_changed"]),
            "covers_changed": len(covers),
            "product_ids_changed": len([change for change in changes if change["type"] == "product_id_changed"]),
            "slots_moved": len(slot_moves),
        },
        "changes": changes,
    }


def _save_success_message(
    additions: int,
    deletions: int,
    covers: int,
    menu_items: int,
    backup_path: Path,
    log_path: Path | None,
    log_error: Exception | None = None,
) -> str:
    if covers and not additions and not deletions:
        title = "Carátulas guardadas en la SD."
    elif additions or deletions:
        title = "Cambios de juegos aplicados en la SD."
    else:
        title = "Menú OpenMenu actualizado."

    lines = [
        title,
        "",
        f"Menú reconstruido: {menu_items} juegos.",
    ]
    if covers:
        lines.append(f"Carátulas sincronizadas: {covers}.")
    if additions:
        lines.append(f"Juegos agregados: {additions}.")
    if deletions:
        lines.append(f"Juegos eliminados: {deletions}.")
    lines.extend([
        "",
        f"Backup de 01:",
        str(backup_path),
    ])
    if log_path is not None:
        lines.extend(["", "Registro:", str(log_path)])
    elif log_error is not None:
        lines.extend(["", f"Advertencia: no se pudo actualizar el registro ({log_error})."])
    return "\n".join(lines)


def _planned_slot_moves(games: list[GameItem]) -> list[dict]:
    plan = SdSlotTransactionService(Path("."), "preview").build_plan(games)
    return [
        {
            "old_slot": int(entry.old_slot),
            "new_slot": int(entry.new_slot),
            "name": entry.name,
            "product_id": entry.product_id,
        }
        for entry in plan.moves
    ]


def _slot_folder(root_path: Path, slot: int) -> Path:
    return Path(root_path) / f"{slot:02d}"


def _compact_game_slots(root_path: Path, games: list[GameItem]) -> list[dict]:
    service = SdSlotTransactionService(root_path, "test_compaction")
    plan = service.build_plan(games)
    return [
        {
            "old_slot": int(entry.old_slot),
            "new_slot": int(entry.new_slot),
            "name": entry.name,
            "product_id": entry.product_id,
        }
        for entry in service.execute(plan, games).plan.moves
    ]


class SearchWorker(QObject):
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, game: GameItem, query: str):
        super().__init__()
        self.game = game
        self.query = query

    def run(self):
        try:
            log.info("SearchWorker started: slot=%03d query=%s", self.game.slot, self.query)
            try:
                previous = load_saved_candidates(self.game)
            except Exception:
                log.exception("Could not read cover library before search")
                previous = []
            candidates = find_candidates(self.game, self.query, include_remote=True, manual_mode=True)
            new_count = count_new_candidates(previous, candidates)
            try:
                search_log_path = append_search_event_for_game(
                    self.game,
                    {
                        "event": "candidate_search",
                        "query": self.query,
                        "result_count": len(candidates),
                        "new_count": new_count,
                        "saved_count": len(previous),
                        "results": summarize_candidates(candidates),
                    },
                )
                if search_log_path is not None:
                    log.info("SD search log updated: %s", search_log_path)
            except Exception:
                log.exception("Could not write SD search log")
            self.finished.emit({
                "candidates": candidates,
                "new_count": new_count,
                "saved_count": len(previous),
            })
        except Exception as exc:
            log.exception("SearchWorker failed")
            try:
                append_search_event_for_game(
                    self.game,
                    {
                        "event": "candidate_search_error",
                        "query": self.query,
                        "error": str(exc),
                    },
                )
            except Exception:
                log.exception("Could not write failed SD search log")
            self.error.emit(str(exc))


class AddGamesWorker(QObject):
    progress = Signal(int, int, str, str)
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, entries: list[RomLibraryEntry], games: list[GameItem],
                 slot_cover_map: dict[int, int], product_cover_map: dict[str, int],
                 state: dict, root_path: Path):
        super().__init__()
        self.entries = entries
        self.games = list(games)
        self.slot_cover_map = dict(slot_cover_map)
        self.product_cover_map = dict(product_cover_map)
        self.state = state
        self.root_path = Path(root_path)

    def run(self):
        try:
            added: list[GameItem] = []
            skipped = 0
            total = max(1, len(self.entries))
            working = list(self.games)
            for index, entry in enumerate(self.entries, 1):
                self.progress.emit(index, total, entry.name, f"Preparando juego {index} de {total}")
                slot = next_free_slot(working)
                if slot is None:
                    skipped += 1
                    continue
                game = build_pending_game(
                    entry,
                    slot,
                    self.slot_cover_map.get(slot) or self.product_cover_map.get((entry.product_id or "").upper()),
                )
                self._seed_cover_for_new_game(game)
                working.append(game)
                working.sort(key=lambda item: item.slot)
                added.append(game)
            self.finished.emit({"games": added, "skipped": skipped})
        except Exception as exc:
            log.exception("AddGamesWorker failed")
            self.error.emit(str(exc))

    def _seed_cover_for_new_game(self, game: GameItem):
        try:
            candidate = best_auto_candidate(game, game.name, include_remote=False)
            if candidate is not None:
                image = load_candidate_image(candidate)
                quality = analyze_image(image)
                persist_cover_selection(
                    game,
                    candidate,
                    image,
                    quality,
                    "seleccionada",
                    state_path=STATE_PATH,
                    state=self.state,
                    root_path=self.root_path,
                    persist_state=False,
                )
                game.has_placeholder_cover = False
                return
        except Exception:
            log.exception("Could not resolve local cover for new game: slot=%03d", game.slot)

        placeholder_path = ensure_no_cover_asset()
        game.current_cover = placeholder_path
        game.selected_image = ""
        game.original_image = ""
        game.preview_image = ""
        game.selected_source = ""
        game.selected_score = 0
        game.quality_label = ""
        game.quality_score = 0
        game.status = "faltante"
        game.has_placeholder_cover = True


class BulkWorker(QObject):
    progress = Signal(int, int, str, str)
    proposal = Signal(object)
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, games: list[GameItem]):
        super().__init__()
        self.games = games
        self.cancelled = False

    def cancel(self):
        self.cancelled = True

    def run(self):
        summary = {
            "processed": 0,
            "auto": 0,
            "review": 0,
            "skipped": 0,
            "errors": 0,
            "cancelled": False,
            "providers": {},
        }
        total = len(self.games)
        settings = load_settings()
        try:
            log.info("Bulk search started: %s targets", total)
            for index, game in enumerate(self.games, start=1):
                if self.cancelled:
                    summary["cancelled"] = True
                    break
                self.progress.emit(index, total, game.name, f"Procesando caratula {index} de {total}")
                summary["processed"] += 1
                try:
                    candidates = find_candidates(game, game.name, include_remote=True)
                    try:
                        append_search_event_for_game(
                            game,
                            {
                                "event": "bulk_candidate_search",
                                "query": game.name,
                                "result_count": len(candidates),
                                "results": summarize_candidates(candidates, limit=5),
                            },
                        )
                    except Exception:
                        log.exception("Could not write bulk SD search log")
                    candidate = candidates[0] if candidates else None
                    if candidate is None:
                        summary["skipped"] += 1
                        self.proposal.emit(BulkProposal(game.slot, status="omitida", reason="sin candidato confiable"))
                        continue
                    provider_id = source_provider_id(candidate.source)
                    summary["providers"][provider_id] = summary["providers"].get(provider_id, 0) + 1
                    image = load_candidate_image(candidate)
                    quality = analyze_image(image)
                    if not quality.accepted:
                        summary["skipped"] += 1
                        self.proposal.emit(BulkProposal(game.slot, candidate, image, quality, "omitida", "calidad rechazada"))
                        continue
                    min_auto = provider_threshold(settings, provider_id, "min_auto_score", 86)
                    if candidate.product_match or candidate.alias_match or candidate.score >= min_auto:
                        status = "seleccionada"
                        summary["auto"] += 1
                        reason = ""
                    else:
                        status = "revision"
                        summary["review"] += 1
                        reason = f"requiere revision: score {candidate.score} < auto {min_auto}"
                    if quality.label == "Baja" and status == "seleccionada":
                        status = "revision"
                        summary["auto"] -= 1
                        summary["review"] += 1
                        reason = "requiere revision: calidad baja"
                    self.proposal.emit(BulkProposal(game.slot, candidate, image, quality, status, reason))
                except Exception as exc:
                    log.exception("Bulk game failed: slot=%03d", game.slot)
                    try:
                        append_search_event_for_game(
                            game,
                            {
                                "event": "bulk_candidate_search_error",
                                "query": game.name,
                                "error": str(exc),
                            },
                        )
                    except Exception:
                        log.exception("Could not write failed bulk SD search log")
                    summary["errors"] += 1
                    self.proposal.emit(BulkProposal(game.slot, status="error", reason=str(exc)))
            self.finished.emit(summary)
        except Exception as exc:
            log.exception("BulkWorker failed")
            self.error.emit(str(exc))


class SaveChangesWorker(QObject):
    progress = Signal(int, int, str, str)
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, root_path: Path, games: list[GameItem], state: dict, write_allowed: bool = True):
        super().__init__()
        self.root_path = Path(root_path)
        self.games = games
        self.state = state
        self.write_allowed = write_allowed

    def run(self):
        operation_id = new_operation_id()
        transaction_summary: dict | None = None
        try:
            if not self.write_allowed:
                raise PermissionError("La ruta actual esta en modo solo lectura; no se aplicaran cambios.")
            before_metadata = parse_openmenu_from_track(find_openmenu_track(self.root_path))
            deletions = [game for game in self.games if game.pending_delete and game.folder]
            additions = [game for game in self.games if game.pending_add and game.source_path]
            kept = [game for game in self.games if not game.pending_delete]
            cover_targets = [
                game
                for game in kept
                if not game.has_placeholder_cover
                and game.selected_image
                and Path(game.selected_image).exists()
                and game.save_status == "pendiente_guardar"
            ]
            renamed_targets = [
                game
                for game in kept
                if game.save_status == "pendiente_guardar"
                and before_metadata.get(game.slot, {}).get("name", "") not in {"", game.name}
            ]
            product_targets = [
                game
                for game in kept
                if game.save_status == "pendiente_guardar"
                and before_metadata.get(game.slot, {}).get("product", "") not in {"", game.product_id}
            ]
            slot_service = SdSlotTransactionService(self.root_path, operation_id)
            slot_plan = slot_service.build_plan(self.games)
            slot_moves = [
                {
                    "old_slot": int(entry.old_slot),
                    "new_slot": int(entry.new_slot),
                    "name": entry.name,
                    "product_id": entry.product_id,
                }
                for entry in slot_plan.moves
            ]
            transaction_summary = _save_transaction_summary(
                self.root_path,
                additions,
                deletions,
                renamed_targets,
                cover_targets,
                product_targets,
                slot_moves,
                before_metadata,
            )
            append_transaction(
                self.root_path,
                {
                    "operation_id": operation_id,
                    "operation": "save_changes",
                    "result": "pending",
                    **transaction_summary,
                },
            )
            total = max(1, len(deletions) + len(additions) + 1)
            current = 0

            slot_result = slot_service.execute(slot_plan, self.games, progress=self.progress.emit)
            if slot_result.product_updates and transaction_summary is not None:
                changes = transaction_summary.setdefault("changes", [])
                for update in slot_result.product_updates:
                    changes.append({"type": "product_id_changed", **update})
                summary = transaction_summary.setdefault("summary", {})
                summary["product_ids_changed"] = len([
                    change for change in changes if change.get("type") == "product_id_changed"
                ])
                summary["slot_transaction"] = str(slot_result.transaction_dir)
                summary["trash_dir"] = str(slot_result.trash_dir)
            for game in deletions:
                drop_game_state(self.state, self.root_path, game.slot)
            kept = [game for game in self.games if not game.pending_delete]

            current += 1
            self.progress.emit(current, total, "Menu OpenMenu", f"Reconstruyendo menu {current} de {total}")
            write_openmenu_ini(kept)
            rebuild_result = OpenMenuRebuilder().rebuild_and_replace(self.root_path, kept)

            for game in kept:
                if game.pending_delete:
                    continue
                if game.save_status:
                    game.save_status = "guardado"
                patch_game_state(self.state, self.root_path, game)
            flush_state(STATE_PATH, self.state)

            log_path = None
            log_error = None
            try:
                log_path = append_transaction(
                    self.root_path,
                    {
                        "operation_id": operation_id,
                        "operation": "save_changes",
                        "result": "success",
                        "menu_backup": str(rebuild_result.backup_slot),
                        "menu_items": rebuild_result.num_items,
                        **(transaction_summary or {}),
                    },
                )
            except Exception as log_exc:
                log.exception("Could not write success transaction")
                log_error = log_exc
            self.finished.emit(
                _save_success_message(
                    additions=len(additions),
                    deletions=len(deletions),
                    covers=len(cover_targets),
                    menu_items=rebuild_result.num_items,
                    backup_path=rebuild_result.backup_slot,
                    log_path=log_path,
                    log_error=log_error,
                )
            )
        except Exception as exc:
            log.exception("SaveChangesWorker failed")
            try:
                append_transaction(
                    self.root_path,
                    {
                        "operation_id": operation_id,
                        "operation": "save_changes",
                        "result": "failed",
                        "error": str(exc),
                        **(transaction_summary or {"root": str(self.root_path.resolve())}),
                    },
                )
            except Exception:
                log.exception("Could not write failed transaction")
            self.error.emit(str(exc))


class SaveBulkWorker(QObject):
    progress = Signal(int, int, str)
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, items: list[tuple]):
        super().__init__()
        self.items = items

    def run(self):
        results = []
        total = len(self.items)
        try:
            for idx, (game, proposal) in enumerate(self.items, 1):
                self.progress.emit(idx, total, game.name)
                try:
                    base_name = safe_filename(game.slot, game.name)
                    orig, norm, prev, quality = save_cover_set(
                        proposal.image,
                        base_name,
                        INBOX_ORIGINALS_DIR,
                        INBOX_NORMALIZED_DIR,
                        INBOX_PREVIEW_DIR,
                    )
                    results.append({
                        "slot": game.slot,
                        "status": "dudosa" if proposal.status == "dudosa" else "seleccionada",
                        "original": str(orig),
                        "normalized": str(norm),
                        "preview": str(prev),
                        "source": proposal.candidate.source,
                        "score": proposal.candidate.score,
                        "quality": quality,
                        "error": "",
                    })
                except Exception as exc:
                    log.exception("SaveBulkWorker: slot=%03d failed", game.slot)
                    results.append({"slot": game.slot, "error": str(exc)})
            self.finished.emit(results)
        except Exception as exc:
            log.exception("SaveBulkWorker fatal")
            self.error.emit(str(exc))

