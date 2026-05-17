from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from ..config.settings import configured_openmenu_template_dir, load_settings
from ..dreamcast.storage_diagnostics import ROUTE_EMPTY_SAFE, StorageDiagnostic, diagnose_storage
from .openmenu_rebuilder import OpenMenuRebuildError, OpenMenuRebuilder, config_from_settings


class OpenMenuSetupError(RuntimeError):
    """Raised when an empty SD cannot be prepared safely."""

    def __init__(self, message: str, key: str = "", **params: object):
        super().__init__(message)
        self.key = key
        self.params = params


def install_openmenu_base(root: Path, settings: dict | None = None) -> StorageDiagnostic:
    root = Path(root)
    diagnostic = diagnose_storage(root)
    if diagnostic.route_class != ROUTE_EMPTY_SAFE or not diagnostic.prepare_allowed:
        raise OpenMenuSetupError(
            "La ruta ya no esta vacia o no es segura para preparar.",
            "dialog.setup.error.path_not_empty",
        )

    settings = settings or load_settings()
    template_dir = configured_openmenu_template_dir(settings)
    source_slot = template_dir / "01"
    target_slot = root / "01"
    if target_slot.exists():
        raise OpenMenuSetupError(
            f"El slot base ya existe y no se sobrescribira: {target_slot}",
            "dialog.setup.error.slot_exists",
            path=target_slot,
        )

    try:
        if source_slot.is_dir():
            shutil.copytree(source_slot, target_slot)
        else:
            with tempfile.TemporaryDirectory(prefix="openmenu_base_") as tmp_raw:
                staging_slot = OpenMenuRebuilder(config_from_settings(settings)).prepare_empty_base(Path(tmp_raw))
                if target_slot.exists():
                    raise OpenMenuSetupError(
                        f"El slot base ya existe y no se sobrescribira: {target_slot}",
                        "dialog.setup.error.slot_exists",
                        path=target_slot,
                    )
                shutil.copytree(staging_slot, target_slot)
    except OpenMenuSetupError:
        raise
    except (OpenMenuRebuildError, OSError) as exc:
        raise OpenMenuSetupError(
            f"No se pudo copiar OpenMenu base: {exc}",
            "dialog.setup.error.copy_failed",
            message=exc,
        ) from exc

    return diagnose_storage(root)
