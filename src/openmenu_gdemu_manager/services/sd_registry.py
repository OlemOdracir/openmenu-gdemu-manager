from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .. import __version__


SD_REGISTRY_DIR_NAME = "_openmenu_gdemu_manager"
BACKUP_REGISTRY_FILE_NAME = "backup_registry.json"
BACKUP_REGISTRY_SCHEMA_VERSION = 1


def registry_dir(root: Path) -> Path:
    return Path(root) / SD_REGISTRY_DIR_NAME


def backup_registry_path(root: Path) -> Path:
    return registry_dir(root) / BACKUP_REGISTRY_FILE_NAME


def read_backup_registry(root: Path) -> dict[str, Any] | None:
    path = backup_registry_path(root)
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def last_backup_path(root: Path) -> Path | None:
    registry = read_backup_registry(root)
    if not registry:
        return None
    last_backup = registry.get("last_backup")
    if not isinstance(last_backup, dict):
        return None
    raw_path = str(last_backup.get("path", "") or "").strip()
    return Path(raw_path) if raw_path else None


def registered_backup_exists(root: Path) -> bool:
    path = last_backup_path(root)
    return bool(path and path.is_dir())


def write_backup_registry(root: Path, backup_path: Path, app_version: str = __version__) -> Path:
    root = Path(root)
    backup_path = Path(backup_path)
    path = backup_registry_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "schema_version": BACKUP_REGISTRY_SCHEMA_VERSION,
        "last_backup": {
            "path": str(backup_path.resolve()),
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "app_version": app_version,
            "source_root": str(root.resolve()),
        },
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
