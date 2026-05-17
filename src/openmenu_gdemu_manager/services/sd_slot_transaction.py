from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from ..core.models import GameItem
from ..dreamcast.metadata import is_synthetic_slot_serial, read_disc_product_id
from ..dreamcast.sd_writer import copy_game_source, source_size, write_name_txt
from .sd_registry import registry_dir


ProgressCallback = Callable[[int, int, str, str], None]


@dataclass(frozen=True)
class SlotPlanEntry:
    action: str
    name: str
    old_slot: int | None
    new_slot: int | None
    product_id: str
    source_path: str = ""
    folder: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "name": self.name,
            "old_slot": self.old_slot,
            "new_slot": self.new_slot,
            "product_id": self.product_id,
            "source_path": self.source_path,
            "folder": self.folder,
        }


@dataclass(frozen=True)
class SlotTransactionPlan:
    operation_id: str
    entries: list[SlotPlanEntry]

    @property
    def additions(self) -> list[SlotPlanEntry]:
        return [entry for entry in self.entries if entry.action == "add"]

    @property
    def deletions(self) -> list[SlotPlanEntry]:
        return [entry for entry in self.entries if entry.action == "delete"]

    @property
    def moves(self) -> list[SlotPlanEntry]:
        return [entry for entry in self.entries if entry.action == "move"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "operation_id": self.operation_id,
            "entries": [entry.to_dict() for entry in self.entries],
        }


@dataclass(frozen=True)
class SlotTransactionResult:
    plan: SlotTransactionPlan
    transaction_dir: Path
    trash_dir: Path
    moved: list[dict[str, Any]]
    deleted: list[dict[str, Any]]
    added: list[dict[str, Any]]
    product_updates: list[dict[str, Any]]


class SdSlotTransactionService:
    def __init__(self, root_path: Path, operation_id: str):
        self.root_path = Path(root_path)
        self.operation_id = operation_id
        self.transaction_dir = registry_dir(self.root_path) / "slot_transactions" / operation_id
        self.temp_dir = self.transaction_dir / "temp"
        self.add_dir = self.transaction_dir / "add"
        self.trash_dir = registry_dir(self.root_path) / "trash" / operation_id

    def build_plan(self, games: list[GameItem]) -> SlotTransactionPlan:
        entries: list[SlotPlanEntry] = []
        active = [game for game in games if not game.pending_delete]
        final_slots = {id(game): index for index, game in enumerate(active, start=2)}

        for game in sorted(games, key=lambda item: item.slot):
            if game.pending_delete:
                entries.append(SlotPlanEntry(
                    action="delete",
                    name=game.name,
                    old_slot=game.slot,
                    new_slot=None,
                    product_id=game.product_id,
                    folder=str(game.folder or self._slot_folder(game.slot)),
                ))
                continue
            new_slot = final_slots[id(game)]
            old_slot = game.slot
            if game.pending_add:
                action = "add"
            elif old_slot != new_slot:
                action = "move"
            else:
                action = "keep"
            entries.append(SlotPlanEntry(
                action=action,
                name=game.name,
                old_slot=old_slot,
                new_slot=new_slot,
                product_id=game.product_id,
                source_path=str(game.source_path or ""),
                folder=str(game.folder or self._slot_folder(old_slot)),
            ))
        return SlotTransactionPlan(self.operation_id, entries)

    def can_auto_recover(self) -> bool:
        try:
            self._read_plan()
            self._read_state_strict()
            return True
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            return False

    def execute(
        self,
        plan: SlotTransactionPlan,
        games: list[GameItem],
        progress: ProgressCallback | None = None,
    ) -> SlotTransactionResult:
        self._validate_plan_paths(plan)
        self.transaction_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.add_dir.mkdir(parents=True, exist_ok=True)
        self.trash_dir.mkdir(parents=True, exist_ok=True)
        self._write_json("plan.json", plan.to_dict())
        self._write_state("planned")

        moved: list[dict[str, Any]] = []
        deleted: list[dict[str, Any]] = []
        added: list[dict[str, Any]] = []
        product_updates: list[dict[str, Any]] = []
        game_by_old_slot = {game.slot: game for game in games}

        total_steps = max(1, len(plan.deletions) + len(plan.moves) + len(plan.additions) + 1)
        step = 0

        try:
            for entry in plan.deletions:
                step += 1
                self._emit(progress, step, total_steps, entry.name, "Moviendo juego eliminado a papelera interna")
                source = self._path_in_root(Path(entry.folder), "folder origen")
                target = self._path_in_root(self.trash_dir / f"{entry.old_slot:02d}", "papelera interna")
                if source.exists():
                    if target.exists():
                        raise FileExistsError(f"Ya existe papelera para slot {entry.old_slot:03d}: {target}")
                    source.rename(target)
                deleted.append(entry.to_dict() | {"trash_folder": str(target)})
            self._write_state("deleted_to_trash", deleted=deleted)

            temp_by_old_slot: dict[int, Path] = {}
            for entry in plan.moves:
                step += 1
                self._emit(progress, step, total_steps, entry.name, "Moviendo carpeta a temporal")
                source = self._path_in_root(Path(entry.folder), "folder origen")
                temp = self._path_in_root(self.temp_dir / f"{entry.old_slot:02d}", "directorio temporal")
                if source.exists():
                    if temp.exists():
                        raise FileExistsError(f"Ya existe temporal para slot {entry.old_slot:03d}: {temp}")
                    source.rename(temp)
                temp_by_old_slot[int(entry.old_slot)] = temp
            self._write_state("moved_to_temp", deleted=deleted, temp_slots=sorted(temp_by_old_slot))

            for entry in plan.additions:
                step += 1
                self._emit(progress, step, total_steps, entry.name, "Copiando juego nuevo a temporal")
                source_path = Path(entry.source_path)
                temp = self._path_in_root(self.add_dir / f"{entry.new_slot:02d}", "directorio temporal de altas")
                if temp.exists():
                    shutil.rmtree(temp)
                copy_game_source(source_path, temp)
                self._verify_copied_source(source_path, temp)
            self._write_state("added_to_temp", deleted=deleted, temp_slots=sorted(temp_by_old_slot))

            created_slots: list[int] = []
            for entry in plan.moves:
                game = game_by_old_slot[int(entry.old_slot)]
                temp = temp_by_old_slot[int(entry.old_slot)]
                target = self._slot_folder(int(entry.new_slot))
                if target.exists():
                    raise FileExistsError(f"El slot destino ya existe: {target}")
                temp.rename(target)
                update = self._apply_final_slot(game, int(entry.new_slot), target)
                moved.append(entry.to_dict())
                if update:
                    product_updates.append(update)

            for entry in plan.additions:
                game = game_by_old_slot[int(entry.old_slot)]
                temp = self._path_in_root(self.add_dir / f"{entry.new_slot:02d}", "directorio temporal de altas")
                target = self._slot_folder(int(entry.new_slot))
                if target.exists():
                    raise FileExistsError(f"El slot destino ya existe: {target}")
                temp.rename(target)
                update = self._apply_final_slot(game, int(entry.new_slot), target)
                game.pending_add = False
                game.is_new = False
                game.has_placeholder_cover = game.has_placeholder_cover and Path(game.current_cover or "").exists()
                added.append(entry.to_dict())
                created_slots.append(int(entry.new_slot))
                if update:
                    product_updates.append(update)

            self._write_state(
                "moved_to_final",
                deleted=deleted,
                moved=moved,
                added=added,
                created_slots=sorted(created_slots),
            )

            for game in [item for item in games if not item.pending_delete]:
                if game.folder:
                    write_name_txt(Path(game.folder), game.name)

            self._write_state(
                "completed",
                deleted=deleted,
                moved=moved,
                added=added,
                created_slots=sorted(created_slots),
            )
            return SlotTransactionResult(
                plan=plan,
                transaction_dir=self.transaction_dir,
                trash_dir=self.trash_dir,
                moved=moved,
                deleted=deleted,
                added=added,
                product_updates=product_updates,
            )
        except Exception as exc:
            self._write_state("failed", error=str(exc), deleted=deleted, moved=moved, added=added)
            raise

    def complete_from_state(self) -> None:
        self._validate_path_containment()
        plan = self._read_plan()
        self._validate_plan_paths(plan)
        self._write_state("recovering_complete")
        for entry in plan.deletions:
            source = self._path_in_root(Path(entry.folder), "folder origen")
            target = self._path_in_root(self.trash_dir / f"{entry.old_slot:02d}", "papelera interna")
            if source.exists() and not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                source.rename(target)
        for entry in plan.moves:
            original = self._path_in_root(Path(entry.folder), "folder origen")
            temp = self._path_in_root(self.temp_dir / f"{entry.old_slot:02d}", "directorio temporal")
            if original.exists() and not temp.exists():
                temp.parent.mkdir(parents=True, exist_ok=True)
                original.rename(temp)
        for entry in plan.additions:
            temp = self._path_in_root(self.add_dir / f"{entry.new_slot:02d}", "directorio temporal de altas")
            if not temp.exists():
                source_path = Path(entry.source_path)
                temp.parent.mkdir(parents=True, exist_ok=True)
                copy_game_source(source_path, temp)
                self._verify_copied_source(source_path, temp)
        for entry in plan.moves:
            temp = self.temp_dir / f"{entry.old_slot:02d}"
            target = self._slot_folder(int(entry.new_slot))
            if temp.exists() and not target.exists():
                temp.rename(target)
        for entry in plan.additions:
            temp = self._path_in_root(self.add_dir / f"{entry.new_slot:02d}", "directorio temporal de altas")
            target = self._slot_folder(int(entry.new_slot))
            if temp.exists() and not target.exists():
                temp.rename(target)
        self._write_state("completed")

    def revert_from_state(self) -> None:
        self._validate_path_containment()
        plan = self._read_plan()
        self._validate_plan_paths(plan)
        state = self._read_state_strict()
        created_slots = {
            int(value) for value in state.get("created_slots", []) if str(value).strip().isdigit()
        }
        for entry in reversed(plan.entries):
            if entry.action == "move":
                temp = self._path_in_root(self.temp_dir / f"{entry.old_slot:02d}", "directorio temporal")
                original = self._slot_folder(int(entry.old_slot))
                final = self._slot_folder(int(entry.new_slot))
                if temp.exists() and not original.exists():
                    temp.rename(original)
                elif final.exists() and not original.exists():
                    final.rename(original)
            elif entry.action == "delete":
                trash = self._path_in_root(self.trash_dir / f"{entry.old_slot:02d}", "papelera interna")
                original = self._slot_folder(int(entry.old_slot))
                if trash.exists() and not original.exists():
                    trash.rename(original)
            elif entry.action == "add":
                final = self._slot_folder(int(entry.new_slot))
                temp = self._path_in_root(self.add_dir / f"{entry.new_slot:02d}", "directorio temporal de altas")
                if final.exists() and int(entry.new_slot) in created_slots:
                    shutil.rmtree(final)
                if temp.exists():
                    shutil.rmtree(temp)
        self._write_state("reverted", previous_state=state.get("stage", "unknown"))

    def _slot_folder(self, slot: int) -> Path:
        return self._path_in_root(self.root_path / f"{slot:02d}", "slot destino")

    def _apply_final_slot(self, game: GameItem, new_slot: int, folder: Path) -> dict[str, Any] | None:
        old_slot = game.slot
        old_product = game.product_id
        game.slot = new_slot
        game.folder = folder
        if is_synthetic_slot_serial(game.product_id) or not game.product_id:
            new_synthetic = f"SLOT{new_slot:03d}"
            real_product = read_disc_product_id(folder)
            game.product_id = real_product or new_synthetic
            for serial in (old_product, new_synthetic, real_product):
                if serial and serial not in game.artwork_serials:
                    game.artwork_serials.append(serial)
        game.save_status = "pendiente_guardar"
        if old_product != game.product_id:
            return {
                "old_slot": old_slot,
                "new_slot": new_slot,
                "name": game.name,
                "old_product_id": old_product,
                "new_product_id": game.product_id,
                "artwork_aliases": list(game.artwork_serials),
            }
        return None

    def _verify_copied_source(self, source_path: Path, copied_folder: Path) -> None:
        expected = source_size(source_path)
        actual = source_size(copied_folder)
        if expected != actual:
            raise OSError(f"Copia incompleta: {copied_folder} ({actual} != {expected} bytes)")

    def _write_json(self, name: str, payload: dict[str, Any]) -> None:
        path = self.transaction_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = json.dumps(payload, ensure_ascii=False, indent=2)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
            handle.write(raw)
            tmp_path = Path(handle.name)
        tmp_path.replace(path)

    def _write_state(self, stage: str, **extra: Any) -> None:
        self._write_json("state.json", {"stage": stage, "operation_id": self.operation_id, **extra})

    def _read_plan(self) -> SlotTransactionPlan:
        payload = json.loads((self.transaction_dir / "plan.json").read_text(encoding="utf-8"))
        return SlotTransactionPlan(
            operation_id=str(payload["operation_id"]),
            entries=[SlotPlanEntry(**entry) for entry in payload.get("entries", [])],
        )

    def _read_state(self) -> dict[str, Any]:
        try:
            return json.loads((self.transaction_dir / "state.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _read_state_strict(self) -> dict[str, Any]:
        return json.loads((self.transaction_dir / "state.json").read_text(encoding="utf-8"))

    def _validate_path_containment(self) -> None:
        self._path_in_root(self.transaction_dir, "directorio de transacción")
        self._path_in_root(self.temp_dir, "directorio temporal")
        self._path_in_root(self.add_dir, "directorio temporal de altas")
        self._path_in_root(self.trash_dir, "papelera interna")

    def _validate_plan_paths(self, plan: SlotTransactionPlan) -> None:
        self._validate_path_containment()
        for entry in plan.entries:
            if entry.old_slot is not None:
                self._path_in_root(self._slot_folder(int(entry.old_slot)), "slot original")
            if entry.new_slot is not None:
                self._path_in_root(self._slot_folder(int(entry.new_slot)), "slot final")
            if entry.folder:
                self._path_in_root(Path(entry.folder), "folder del plan")

    def _path_in_root(self, path: Path, label: str) -> Path:
        root = self.root_path.resolve()
        resolved = Path(path).resolve()
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"{label} fuera de la SD: {resolved}") from exc
        return resolved

    @staticmethod
    def _emit(progress: ProgressCallback | None, current: int, total: int, name: str, status: str) -> None:
        if progress is not None:
            progress(current, total, name, status)


def incomplete_slot_transactions(root_path: Path) -> list[Path]:
    base = registry_dir(Path(root_path)) / "slot_transactions"
    if not base.exists():
        return []
    result: list[Path] = []
    for tx_dir in sorted([path for path in base.iterdir() if path.is_dir()]):
        state_path = tx_dir / "state.json"
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            result.append(tx_dir)
            continue
        if state.get("stage") not in {"completed", "reverted"}:
            result.append(tx_dir)
    return result
