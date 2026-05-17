"""Compatibility shim for running from the repository root without installation."""

from pathlib import Path


_SRC_PACKAGE = Path(__file__).resolve().parent.parent / "src" / "openmenu_gdemu_manager"
if _SRC_PACKAGE.exists():
    __path__.insert(0, str(_SRC_PACKAGE))

APP_NAME = "OpenMenu GDEMU Manager"
__version__ = "0.2.0-beta.1"
REPOSITORY_URL = "https://github.com/OlemOdracir/openmenu-gdemu-manager"
CONTACT_URL = "https://github.com/OlemOdracir/openmenu-gdemu-manager/issues"
