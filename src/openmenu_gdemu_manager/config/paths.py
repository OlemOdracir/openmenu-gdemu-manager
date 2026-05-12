import os
import shutil
import sys
from pathlib import Path


APP_DIR_NAME = "OpenMenu GDEMU Manager"
PACKAGE_ROOT = Path(__file__).resolve().parents[3]


def _bundled_buildgdi_path() -> Path:
    candidates: list[Path] = []
    pyinstaller_root = getattr(sys, "_MEIPASS", "")
    if pyinstaller_root:
        candidates.append(Path(pyinstaller_root) / "third_party" / "buildgdi" / "buildgdi.exe")
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / "_internal" / "third_party" / "buildgdi" / "buildgdi.exe")
        candidates.append(Path(sys.executable).resolve().parent / "third_party" / "buildgdi" / "buildgdi.exe")
    candidates.append(PACKAGE_ROOT / "third_party" / "buildgdi" / "buildgdi.exe")
    candidates.append(Path(sys.prefix) / "third_party" / "buildgdi" / "buildgdi.exe")
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return candidates[0].resolve() if candidates else (PACKAGE_ROOT / "third_party" / "buildgdi" / "buildgdi.exe")


BUNDLED_BUILDGDI_PATH = _bundled_buildgdi_path()


def _runtime_root() -> Path:
    configured = os.environ.get("OPENMENU_GDEMU_MANAGER_HOME", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA", "").strip()
        if base:
            return (Path(base) / APP_DIR_NAME).resolve()
    return Path.cwd().resolve()


def _documents_root() -> Path:
    configured = os.environ.get("OPENMENU_GDEMU_MANAGER_DOCUMENTS", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    if os.name == "nt":
        user_profile = os.environ.get("USERPROFILE", "").strip()
        if user_profile:
            return (Path(user_profile) / "Documents" / APP_DIR_NAME).resolve()
    return (Path.home() / APP_DIR_NAME).resolve()


BASE_DIR = _runtime_root()
DOCUMENTS_DIR = _documents_root()
DEFAULT_INI = BASE_DIR / "OPENMENU.current.generated.ini"
AUDIT_DIR = BASE_DIR / "_cover_audit_final"
INBOX_DIR = BASE_DIR / "_cover_inbox"
INBOX_ORIGINALS_DIR = INBOX_DIR / "originals"
INBOX_NORMALIZED_DIR = INBOX_DIR / "normalized"
INBOX_PREVIEW_DIR = INBOX_DIR / "preview"
CACHE_DIR = BASE_DIR / "_cover_tool_cache"
MANAGER_CACHE_DIR = BASE_DIR / "_cover_manager_cache"
COVER_LIBRARY_DIR = BASE_DIR / "_cover_library"
STATE_PATH = BASE_DIR / "_cover_manager_state.json"
SETTINGS_PATH = BASE_DIR / "cover_sources.json"
LOG_PATH = BASE_DIR / "openmenu_gdemu_manager.log"
REPORT_TSV = BASE_DIR / "cover_report.tsv"
REPORT_JSON = BASE_DIR / "cover_report.json"
UI_TEMPLATES_DIR = BASE_DIR / "_ui_templates"
LANGUAGES_DIR = BASE_DIR / "languages"
BACKUPS_DIR = DOCUMENTS_DIR / "Backups"

LOCAL_IMAGE_DIRS = [
    BASE_DIR / "images",
    BASE_DIR / "_cover_sources",
    BASE_DIR / "_downloaded_covers",
]


LEGACY_RUNTIME_ITEMS = [
    "cover_sources.json",
    "_cover_manager_state.json",
    "OPENMENU.current.generated.ini",
    "_cover_audit_final",
    "_cover_inbox",
    "_cover_tool_cache",
    "_cover_manager_cache",
    "_cover_library",
    "images",
    "_cover_sources",
    "_downloaded_covers",
    "languages",
]


def migrate_legacy_runtime_data(source_root: Path | None = None) -> list[tuple[Path, Path]]:
    """Copy old project-local runtime data into the current app data folder.

    This is intentionally conservative: it only copies known runtime files/dirs
    and never overwrites data that already exists in the new location.
    """
    source_root = (source_root or Path.cwd()).resolve()
    destination_root = BASE_DIR.resolve()
    if source_root == destination_root:
        return []
    if not _looks_like_legacy_runtime_root(source_root):
        return []

    copied: list[tuple[Path, Path]] = []
    destination_root.mkdir(parents=True, exist_ok=True)
    for name in LEGACY_RUNTIME_ITEMS:
        source = source_root / name
        destination = destination_root / name
        if not source.exists() or destination.exists():
            continue
        try:
            if source.is_dir():
                shutil.copytree(source, destination)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
        except OSError:
            continue
        copied.append((source, destination))
    return copied


def _looks_like_legacy_runtime_root(path: Path) -> bool:
    return (
        (path / "_cover_manager_state.json").exists()
        or (path / "_cover_audit_final").exists()
        or (path / "cover_sources.json").exists()
    )
