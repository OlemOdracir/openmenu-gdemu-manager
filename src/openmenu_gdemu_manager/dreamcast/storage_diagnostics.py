from __future__ import annotations

import ctypes
from dataclasses import dataclass, field
from pathlib import Path

from .metadata import find_openmenu_track


ROUTE_EMPTY_SAFE = "empty_safe"
ROUTE_GDEMU_STRUCTURE = "gdemu_structure"
ROUTE_DANGEROUS = "dangerous_path"
ROUTE_UNKNOWN = "unknown"
ROUTE_LOCAL_BACKUP = "local_backup"

HEALTH_OK = "ok"
HEALTH_NOT_FAT32 = "not_fat32"
HEALTH_POSSIBLE_CORRUPTION = "possible_corruption"
HEALTH_NOT_ACCESSIBLE = "not_accessible"
HEALTH_LOCAL_FOLDER = "local_folder"

MENU_OPENMENU_COMPATIBLE = "openmenu_compatible"
MENU_OPENMENU_OLD = "openmenu_old"
MENU_GDMENU_BASIC = "gdmenu_basic"
MENU_NO_MENU = "no_menu"
MENU_UNKNOWN = "unknown"

IGNORED_EMPTY_NAMES = {
    "_openmenu_gdemu_manager",
    "gdemu.ini",
    "system volume information",
    "$recycle.bin",
    "desktop.ini",
    "indexervolumeguid",
    "wpsettings.dat",
    "wp settings.dat",
    ".spotlight-v100",
    ".trashes",
    ".fseventsd",
}
DANGEROUS_NAMES = {
    "windows",
    "program files",
    "program files (x86)",
    "users",
    "documents and settings",
}
CORRUPTION_NAMES = {"found.000"}


@dataclass
class RouteSummary:
    path: Path
    exists: bool = False
    is_root: bool = False
    drive_type: str = "unknown"
    filesystem: str = ""
    total_bytes: int = 0
    free_bytes: int = 0
    numeric_dirs: list[str] = field(default_factory=list)
    other_entries: list[str] = field(default_factory=list)
    ignored_entries: list[str] = field(default_factory=list)


@dataclass
class MenuDiagnostic:
    state: str = MENU_UNKNOWN
    detail: str = ""


@dataclass
class StorageDiagnostic:
    root: Path
    route_class: str
    storage_health: str
    menu_state: str
    write_allowed: bool
    scan_allowed: bool
    prepare_allowed: bool = False
    reason: str = ""
    warnings: list[str] = field(default_factory=list)
    summary: RouteSummary | None = None
    menu: MenuDiagnostic | None = None

    @property
    def is_blocked(self) -> bool:
        return not self.write_allowed


def diagnose_storage(root: Path) -> StorageDiagnostic:
    root = Path(root)
    summary = _route_summary(root)
    warnings: list[str] = []

    if not summary.exists:
        return _diagnostic(root, ROUTE_UNKNOWN, HEALTH_NOT_ACCESSIBLE, MENU_UNKNOWN, False, False,
                           "La ruta no existe o no es accesible.", warnings, summary)

    try:
        entries = list(root.iterdir())
    except OSError as exc:
        return _diagnostic(root, ROUTE_UNKNOWN, HEALTH_NOT_ACCESSIBLE, MENU_UNKNOWN, False, False,
                           f"No se pudo leer la ruta: {exc}", warnings, summary)

    lowered = {entry.name.lower() for entry in entries}
    if lowered & CORRUPTION_NAMES or any(entry.suffix.lower() == ".chk" for entry in entries if entry.is_file()):
        return _diagnostic(root, ROUTE_UNKNOWN, HEALTH_POSSIBLE_CORRUPTION, MENU_UNKNOWN, False, False,
                           "La ruta presenta señales de corrupcion. La app no intentara reparar ni escribir.",
                           warnings, summary)

    if summary.is_root and summary.drive_type == "fixed":
        return _diagnostic(root, ROUTE_DANGEROUS, HEALTH_OK, MENU_UNKNOWN, False, False,
                           "La ruta parece la raiz de un disco interno. Por seguridad no se usara como SD.",
                           warnings, summary)

    if lowered & DANGEROUS_NAMES:
        return _diagnostic(root, ROUTE_DANGEROUS, HEALTH_OK, MENU_UNKNOWN, False, False,
                           "La ruta contiene carpetas de sistema o datos personales. No parece una SD GDEMU.",
                           warnings, summary)

    if summary.drive_type == "removable" and summary.filesystem and summary.filesystem.upper() != "FAT32":
        return _diagnostic(root, ROUTE_UNKNOWN, HEALTH_NOT_FAT32, MENU_UNKNOWN, False, False,
                           f"La unidad removible usa {summary.filesystem}; GDEMU requiere FAT32.",
                           warnings, summary)

    relevant_entries = [entry for entry in entries if not _is_ignored_empty_entry(entry)]
    if not relevant_entries:
        route_class = ROUTE_EMPTY_SAFE
        health = HEALTH_OK if summary.drive_type == "removable" else HEALTH_LOCAL_FOLDER
        return _diagnostic(root, route_class, health, MENU_NO_MENU, False, False,
                           "La ruta esta vacia. Primero se debe instalar OpenMenu base.",
                           warnings, summary, prepare_allowed=True)

    numeric = [entry for entry in entries if entry.is_dir() and entry.name.isdigit()]
    non_numeric = [entry for entry in relevant_entries if not (entry.is_dir() and entry.name.isdigit())]
    has_gdemu_dirs = any(entry.name == "01" for entry in numeric) and len(numeric) >= 1

    if has_gdemu_dirs:
        menu = detect_menu(root)
        if menu.detail.startswith("No se pudo leer el track openMenu"):
            return _diagnostic(root, ROUTE_GDEMU_STRUCTURE, HEALTH_POSSIBLE_CORRUPTION, menu.state, False, False,
                               "No se pudo leer el track openMenu. La app no intentara reparar ni escribir.",
                               warnings, summary, menu)
        if len(non_numeric) > 20:
            return _diagnostic(root, ROUTE_DANGEROUS, HEALTH_OK, menu.state, False, False,
                               "Hay demasiadas entradas no numericas junto a la estructura GDEMU.",
                               warnings, summary, menu)
        route_class = ROUTE_GDEMU_STRUCTURE if summary.drive_type == "removable" else ROUTE_LOCAL_BACKUP
        health = HEALTH_OK if summary.drive_type == "removable" else HEALTH_LOCAL_FOLDER
        if menu.state == MENU_OPENMENU_COMPATIBLE:
            return _diagnostic(root, route_class, health, menu.state, True, True,
                               "OpenMenu compatible detectado.", warnings, summary, menu)
        if menu.state in {MENU_GDMENU_BASIC, MENU_OPENMENU_OLD}:
            return _diagnostic(root, route_class, health, menu.state, False, True,
                               "La estructura se puede leer, pero requiere migrar o actualizar OpenMenu antes de escribir.",
                               warnings, summary, menu)
        return _diagnostic(root, route_class, health, menu.state, False, True,
                           "La estructura tiene slots, pero el menu no es compatible para escritura.",
                           warnings, summary, menu)

    if summary.is_root or len(relevant_entries) > 20:
        return _diagnostic(root, ROUTE_DANGEROUS, HEALTH_OK, MENU_UNKNOWN, False, False,
                           "La ruta no esta vacia y no tiene estructura GDEMU/OpenMenu.", warnings, summary)

    return _diagnostic(root, ROUTE_UNKNOWN, HEALTH_LOCAL_FOLDER, MENU_UNKNOWN, False, False,
                       "La carpeta no esta vacia y no tiene estructura GDEMU/OpenMenu.", warnings, summary)


def detect_menu(root: Path) -> MenuDiagnostic:
    slot1 = Path(root) / "01"
    if not slot1.exists():
        return MenuDiagnostic(MENU_NO_MENU, "No existe slot 01.")
    menu_track = find_openmenu_track(root)
    if menu_track.exists():
        try:
            with menu_track.open("rb") as handle:
                chunk = handle.read()
        except OSError as exc:
            return MenuDiagnostic(MENU_UNKNOWN, f"No se pudo leer el track openMenu: {exc}")
        if b"[OPENMENU]" in chunk:
            if b"NEODC_1" in chunk or b"openMenu" in chunk or b"OpenMenu" in chunk:
                return MenuDiagnostic(MENU_OPENMENU_COMPATIBLE, "Bloque [OPENMENU] detectado.")
            return MenuDiagnostic(MENU_OPENMENU_OLD, "Bloque [OPENMENU] detectado sin metadata esperada.")
        return MenuDiagnostic(MENU_GDMENU_BASIC, "Slot 01 detectado sin bloque [OPENMENU].")
    if any((slot1 / name).exists() for name in ("disc.gdi", "track03.iso", "1ST_READ.BIN")):
        return MenuDiagnostic(MENU_GDMENU_BASIC, "Slot 01 parece menu GDEMU/gdMenu basico.")
    return MenuDiagnostic(MENU_UNKNOWN, "Slot 01 existe, pero no tiene menu reconocible.")


def _diagnostic(root: Path, route_class: str, health: str, menu_state: str, write_allowed: bool,
                scan_allowed: bool, reason: str, warnings: list[str], summary: RouteSummary,
                menu: MenuDiagnostic | None = None, prepare_allowed: bool = False) -> StorageDiagnostic:
    return StorageDiagnostic(
        root=root,
        route_class=route_class,
        storage_health=health,
        menu_state=menu_state,
        write_allowed=write_allowed,
        scan_allowed=scan_allowed,
        prepare_allowed=prepare_allowed,
        reason=reason,
        warnings=warnings,
        summary=summary,
        menu=menu or MenuDiagnostic(menu_state, reason),
    )


def _route_summary(path: Path) -> RouteSummary:
    path = Path(path)
    resolved = path.resolve() if path.exists() else path
    summary = RouteSummary(path=path, exists=path.exists())
    if not summary.exists:
        return summary
    summary.is_root = _is_drive_root(resolved)
    root = _drive_root(resolved)
    summary.drive_type = _drive_type(root)
    summary.filesystem = _filesystem(root)
    try:
        usage = __import__("shutil").disk_usage(str(root if root.exists() else resolved))
        summary.total_bytes = usage.total
        summary.free_bytes = usage.free
    except OSError:
        pass
    try:
        for entry in path.iterdir():
            if _is_ignored_empty_entry(entry):
                summary.ignored_entries.append(entry.name)
            elif entry.is_dir() and entry.name.isdigit():
                summary.numeric_dirs.append(entry.name)
            else:
                summary.other_entries.append(entry.name)
    except OSError:
        pass
    return summary


def _is_ignored_empty_entry(entry: Path) -> bool:
    name = entry.name.lower()
    return name in IGNORED_EMPTY_NAMES or name.startswith("._")


def _is_drive_root(path: Path) -> bool:
    return bool(path.anchor) and Path(path.anchor).resolve() == path.resolve()


def _drive_root(path: Path) -> Path:
    return Path(path.anchor) if path.anchor else path


def _drive_type(root: Path) -> str:
    if not hasattr(ctypes, "windll"):
        return "unknown"
    value = ctypes.windll.kernel32.GetDriveTypeW(str(root))
    return {
        2: "removable",
        3: "fixed",
        4: "network",
        5: "cdrom",
        6: "ramdisk",
    }.get(value, "unknown")


def _filesystem(root: Path) -> str:
    if not hasattr(ctypes, "windll"):
        return ""
    fs_name = ctypes.create_unicode_buffer(64)
    ok = ctypes.windll.kernel32.GetVolumeInformationW(
        str(root),
        None,
        0,
        None,
        None,
        None,
        fs_name,
        len(fs_name),
    )
    return fs_name.value if ok else ""
