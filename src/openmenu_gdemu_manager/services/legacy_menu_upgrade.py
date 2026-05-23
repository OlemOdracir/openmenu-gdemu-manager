from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from ..dreamcast.scanner import scan_sd_root
from ..dreamcast.storage_diagnostics import (
    HEALTH_LOCAL_FOLDER,
    HEALTH_OK,
    ROUTE_GDEMU_STRUCTURE,
    ROUTE_LOCAL_BACKUP,
    StorageDiagnostic,
    diagnose_storage,
)
from .openmenu_rebuilder import OpenMenuRebuildError, OpenMenuRebuilder, validate_rebuilt_slot
from .transaction_log import append_transaction, new_operation_id


class LegacyMenuUpgradeError(RuntimeError):
    """Raised when a legacy menu cannot be upgraded safely."""


@dataclass(frozen=True)
class LegacyMenuUpgradeResult:
    operation_id: str
    num_items: int
    log_path: Path | None
    diagnostic: StorageDiagnostic


class LegacyMenuUpgradeService:
    """Replace an old slot 01 with a new OpenMenu menu while preserving game slots."""

    def __init__(self, rebuilder: OpenMenuRebuilder | None = None):
        self.rebuilder = rebuilder or OpenMenuRebuilder()

    def upgrade(self, root_path: Path) -> LegacyMenuUpgradeResult:
        root = Path(root_path)
        operation_id = new_operation_id()
        diagnostic = self._validate_migratable(root)
        games = scan_sd_root(root, state=None)
        payload = {
            "operation_id": operation_id,
            "operation": "legacy_menu_upgrade",
            "root": str(root.resolve()),
            "detected_menu_state": diagnostic.menu_state,
            "games_found": len(games),
        }
        log_path = append_transaction(root, {"result": "pending", **payload})

        try:
            with tempfile.TemporaryDirectory(prefix="openmenu_legacy_upgrade_") as tmp_raw:
                staging_slot = self.rebuilder.prepare_from_template(games, Path(tmp_raw))
                self._replace_legacy_slot(root, staging_slot, len(games))
            final_diagnostic = diagnose_storage(root)
            if not final_diagnostic.write_allowed:
                raise LegacyMenuUpgradeError(
                    f"OpenMenu fue reemplazado, pero el diagnostico final no quedo compatible: "
                    f"{final_diagnostic.reason}"
                )
            log_path = append_transaction(
                root,
                {
                    "result": "success",
                    "menu_items": len(games),
                    "old_menu_deleted": True,
                    **payload,
                },
            )
            return LegacyMenuUpgradeResult(operation_id, len(games), log_path, final_diagnostic)
        except Exception as exc:
            append_transaction(
                root,
                {
                    "result": "failed",
                    "error": str(exc),
                    **payload,
                },
            )
            if isinstance(exc, LegacyMenuUpgradeError):
                raise
            raise LegacyMenuUpgradeError(str(exc)) from exc

    def _validate_migratable(self, root: Path) -> StorageDiagnostic:
        diagnostic = diagnose_storage(root)
        if not diagnostic.legacy_menu_migratable:
            raise LegacyMenuUpgradeError("La SD no tiene un menu antiguo migrable.")
        if diagnostic.route_class not in {ROUTE_GDEMU_STRUCTURE, ROUTE_LOCAL_BACKUP}:
            raise LegacyMenuUpgradeError("La ruta no tiene estructura GDEMU/OpenMenu valida.")
        if diagnostic.storage_health not in {HEALTH_OK, HEALTH_LOCAL_FOLDER}:
            raise LegacyMenuUpgradeError(f"La ruta no esta en buen estado: {diagnostic.storage_health}")
        current_slot = root / "01"
        if not current_slot.is_dir():
            raise LegacyMenuUpgradeError(f"No existe la carpeta 01 para actualizar: {current_slot}")
        self._ensure_child(root, current_slot)
        return diagnostic

    def _replace_legacy_slot(self, root: Path, staging_slot: Path, expected_items: int) -> None:
        root = root.resolve()
        staging_slot = Path(staging_slot)
        current_slot = root / "01"
        pending_slot = root / "01.new"
        self._ensure_child(root, current_slot)
        self._ensure_child(root, pending_slot)
        validate_rebuilt_slot(staging_slot, expected_items=expected_items)
        if pending_slot.exists():
            shutil.rmtree(pending_slot)
        shutil.copytree(staging_slot, pending_slot)
        validate_rebuilt_slot(pending_slot, expected_items=expected_items)
        activated = False
        try:
            shutil.rmtree(current_slot)
            pending_slot.rename(current_slot)
            validate_rebuilt_slot(current_slot, expected_items=expected_items)
            activated = True
        except Exception as exc:
            if not current_slot.exists() and pending_slot.exists():
                try:
                    pending_slot.rename(current_slot)
                    validate_rebuilt_slot(current_slot, expected_items=expected_items)
                    activated = True
                except Exception:
                    pass
            raise LegacyMenuUpgradeError(
                "No se pudo activar el nuevo OpenMenu. La carpeta 01.new puede contener la copia validada."
            ) from exc
        finally:
            if activated and pending_slot.exists():
                shutil.rmtree(pending_slot, ignore_errors=True)

    @staticmethod
    def _ensure_child(root: Path, path: Path) -> None:
        root_resolved = Path(root).resolve()
        path_resolved = Path(path).resolve()
        if path_resolved != root_resolved and root_resolved not in path_resolved.parents:
            raise LegacyMenuUpgradeError(f"Ruta fuera de la SD: {path_resolved}")
