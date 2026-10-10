"""Compatibility shim for running from the repository root without installation."""

from pathlib import Path


_SRC_PACKAGE = Path(__file__).resolve().parent.parent / "src" / "openmenu_gdemu_manager"
if _SRC_PACKAGE.exists():
    __path__.insert(0, str(_SRC_PACKAGE))

from ._metadata import APP_NAME, CONTACT_URL, REPOSITORY_URL, __version__
