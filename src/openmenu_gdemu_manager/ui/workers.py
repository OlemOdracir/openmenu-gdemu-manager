import logging
import json
import urllib.request
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
from ..covers.providers.registry import provider_threshold, source_provider_id
from ..config.settings import load_settings
from ..dreamcast.sd_writer import (
    copy_game_source, patch_track05_cover, patch_track05_menu,
    send_to_recycle_bin, source_size, validate_track05_menu_capacity, write_name_txt, write_openmenu_ini,
)
from ..config.state import drop_game_state, flush_state, patch_game_state
from ..dreamcast.storage_diagnostics import diagnose_storage
from ..services.cover_service import persist_cover_selection
from ..services.cover_library import count_new_candidates, load_saved_candidates
from ..services.game_service import build_pending_game, next_free_slot

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


class UpdateCheckWorker(QObject):
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, current_version: str):
        super().__init__()
        self.current_version = current_version

    def run(self):
        try:
            request = urllib.request.Request(
                GITHUB_LATEST_RELEASE_API,
                headers={
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "OpenMenu-GDEMU-Manager",
                },
            )
            with urllib.request.urlopen(request, timeout=6) as response:
                payload = json.loads(response.read().decode("utf-8"))
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
            self.finished.emit({
                "candidates": candidates,
                "new_count": count_new_candidates(previous, candidates),
                "saved_count": len(previous),
            })
        except Exception as exc:
            log.exception("SearchWorker failed")
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
        try:
            if not self.write_allowed:
                raise PermissionError("La ruta actual esta en modo solo lectura; no se aplicaran cambios.")
            deletions = [game for game in self.games if game.pending_delete and game.folder]
            additions = [game for game in self.games if game.pending_add and game.source_path]
            kept = [game for game in self.games if not game.pending_delete]
            validate_track05_menu_capacity(self.root_path / "01" / "track05.iso", kept)
            cover_targets = [
                game
                for game in kept
                if game.cover_index is not None
                and not game.has_placeholder_cover
                and (game.selected_image or game.current_cover)
                and Path(game.selected_image or game.current_cover or "").exists()
            ]
            total = max(1, len(deletions) + len(additions) + len(cover_targets) + 1)
            current = 0

            for game in deletions:
                current += 1
                self.progress.emit(current, total, game.name, f"Eliminando juego {current} de {total}")
                send_to_recycle_bin(Path(game.folder))
                drop_game_state(self.state, self.root_path, game.slot)

            for game in additions:
                current += 1
                add_index = additions.index(game) + 1
                add_total = len(additions)
                total_bytes = source_size(Path(game.source_path))
                self.progress.emit(
                    current,
                    total,
                    game.name,
                    f"Copiando juego {add_index} de {add_total}",
                )
                slot_folder = self.root_path / f"{game.slot:02d}"

                def _copy_progress(file_name: str, copied: int, total_copy: int,
                                   index: int = add_index, count: int = add_total,
                                   title: str = game.name, expected: int = total_bytes) -> None:
                    total_for_percent = total_copy or expected
                    if total_for_percent > 0:
                        percent = min(100, int((copied / total_for_percent) * 100))
                        detail = f"{title} - {percent}% ({copied // (1024 * 1024)} / {total_for_percent // (1024 * 1024)} MB)"
                    else:
                        detail = f"{title} - {file_name}"
                    self.progress.emit(
                        current,
                        total,
                        detail,
                        f"Copiando juego {index} de {count}",
                    )

                copy_game_source(Path(game.source_path), slot_folder, progress=_copy_progress)
                write_name_txt(slot_folder, game.name)
                game.folder = slot_folder
                game.pending_add = False
                game.is_new = False
                game.save_status = "guardado"
                game.has_placeholder_cover = game.has_placeholder_cover and Path(game.current_cover or "").exists()

            for game in kept:
                if game.folder:
                    write_name_txt(Path(game.folder), game.name)

            current += 1
            self.progress.emit(current, total, "Menu OpenMenu", f"Actualizando menu {current} de {total}")
            write_openmenu_ini(kept)
            patch_track05_menu(self.root_path / "01" / "track05.iso", kept)

            for game in cover_targets:
                current += 1
                image_path = Path(game.selected_image or game.current_cover or "")
                self.progress.emit(current, total, game.name, f"Aplicando caratula {current} de {total}")
                patch_track05_cover(self.root_path / "01" / "track05.iso", int(game.cover_index), image_path)
                if game.folder:
                    game.current_cover = image_path

            for game in kept:
                if game.pending_delete:
                    continue
                if game.save_status:
                    game.save_status = "guardado"
                patch_game_state(self.state, self.root_path, game)
            flush_state(STATE_PATH, self.state)

            self.finished.emit(
                f"Cambios aplicados: {len(additions)} juegos agregados, "
                f"{len(deletions)} juegos eliminados y {len(cover_targets)} caratulas sincronizadas."
            )
        except Exception as exc:
            log.exception("SaveChangesWorker failed")
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

