from __future__ import annotations

import shutil
from pathlib import Path

from ..config.settings import configured_openmenu_template_dir, load_settings
from ..dreamcast.storage_diagnostics import ROUTE_EMPTY_SAFE, StorageDiagnostic, diagnose_storage


class OpenMenuSetupError(RuntimeError):
    """Raised when an empty SD cannot be prepared safely."""


def install_openmenu_base(root: Path, settings: dict | None = None) -> StorageDiagnostic:
    root = Path(root)
    diagnostic = diagnose_storage(root)
    if diagnostic.route_class != ROUTE_EMPTY_SAFE or not diagnostic.prepare_allowed:
        raise OpenMenuSetupError("La ruta ya no esta vacia o no es segura para preparar.")

    settings = settings or load_settings()
    template_dir = configured_openmenu_template_dir(settings)
    source_slot = template_dir / "01"
    target_slot = root / "01"
    if not source_slot.is_dir():
        raise OpenMenuSetupError(f"No se encontro la plantilla OpenMenu base: {source_slot}")
    if target_slot.exists():
        raise OpenMenuSetupError(f"El slot base ya existe y no se sobrescribira: {target_slot}")

    try:
        shutil.copytree(source_slot, target_slot)
    except OSError as exc:
        raise OpenMenuSetupError(f"No se pudo copiar OpenMenu base: {exc}") from exc

    return diagnose_storage(root)
