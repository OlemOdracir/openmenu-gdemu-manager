from __future__ import annotations

import json
import os
import shutil
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Callable

from ..config.paths import BACKUPS_DIR
from ..dreamcast.storage_diagnostics import StorageDiagnostic


class BackupError(RuntimeError):
    """Raised when a safe SD backup cannot be created."""


ProgressCallback = Callable[[int, int, str], None]


def suggested_backup_dir(source: Path, base_dir: Path | None = None) -> Path:
    source = Path(source)
    base_dir = base_dir or _default_backup_base_dir()
    drive = source.drive.rstrip(":\\") or "folder"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return base_dir / f"SD_{drive}_{stamp}"


def _default_backup_base_dir() -> Path:
    if os.name == "nt":
        user_profile = os.environ.get("USERPROFILE", "").strip()
        if user_profile:
            return Path(user_profile) / "Documents" / "OpenMenu GDEMU Manager" / "Backups"
    return BACKUPS_DIR


def backup_sd_contents(source: Path, destination: Path, progress: ProgressCallback | None = None) -> Path:
    source = Path(source).resolve()
    destination = Path(destination).resolve()
    if not source.exists() or not source.is_dir():
        raise BackupError(f"La ruta origen no existe o no es carpeta: {source}")
    _ensure_not_inside_source(source, destination)
    destination.mkdir(parents=True, exist_ok=True)

    files = [path for path in source.rglob("*") if path.is_file()]
    total = max(1, len(files))
    copied = 0
    total_bytes = 0
    copied_files: list[dict[str, object]] = []
    for file_path in files:
        relative = file_path.relative_to(source)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file_path, target)
        size = target.stat().st_size
        total_bytes += size
        copied += 1
        copied_files.append({"path": str(relative).replace("\\", "/"), "bytes": size})
        if progress:
            progress(copied, total, str(relative))

    for folder in source.rglob("*"):
        if folder.is_dir():
            (destination / folder.relative_to(source)).mkdir(parents=True, exist_ok=True)

    manifest = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source": str(source),
        "destination": str(destination),
        "file_count": copied,
        "total_bytes": total_bytes,
        "files": copied_files,
    }
    (destination / "backup_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return destination


def backup_decision_key(diagnostic: StorageDiagnostic) -> str:
    summary = diagnostic.summary
    basis = {
        "root": str(Path(diagnostic.root).resolve()).lower(),
        "route_class": diagnostic.route_class,
        "menu_state": diagnostic.menu_state,
        "numeric_dirs": sorted(summary.numeric_dirs if summary else []),
        "other_entries": sorted(summary.other_entries if summary else []),
    }
    raw = json.dumps(basis, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def backup_decision(settings: dict, diagnostic: StorageDiagnostic) -> dict | None:
    return settings.get("ui", {}).get("backup_decisions", {}).get(backup_decision_key(diagnostic))


def set_backup_decision(settings: dict, diagnostic: StorageDiagnostic, decision: str,
                        destination: Path | None = None) -> dict:
    settings.setdefault("ui", {})
    settings["ui"].setdefault("backup_decisions", {})
    settings["ui"]["backup_decisions"][backup_decision_key(diagnostic)] = {
        "decision": decision,
        "root": str(Path(diagnostic.root).resolve()),
        "destination": str(destination.resolve()) if destination else "",
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    return settings


def _ensure_not_inside_source(source: Path, destination: Path) -> None:
    try:
        destination.relative_to(source)
    except ValueError:
        return
    raise BackupError("El respaldo no puede quedar dentro de la SD/origen.")
