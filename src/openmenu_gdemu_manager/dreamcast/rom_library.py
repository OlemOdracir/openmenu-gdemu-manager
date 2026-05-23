from __future__ import annotations

from pathlib import Path

from ..core.matching import normalize
from .metadata import (
    detect_media_type,
    is_descriptive_game_name,
    parse_openmenu_ini,
    read_disc_internal_name_from_image,
    read_disc_product_id,
    read_disc_product_id_from_image,
    read_name_txt,
    resolve_game_display_name,
)
from ..core.models import GameItem, RomLibraryEntry
from ..config.paths import DEFAULT_INI
from ..config.settings import configured_rom_dirs, supported_media_types


def scan_rom_library(settings: dict, existing_games: list[GameItem]) -> list[RomLibraryEntry]:
    supported = supported_media_types(settings)
    existing_names = {normalize(game.name) for game in existing_games}
    existing_products = {game.product_id.upper() for game in existing_games if game.product_id}
    known = _known_metadata()
    results: dict[str, RomLibraryEntry] = {}
    for root in configured_rom_dirs(settings):
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if _is_inside_gdemu_menu_slot(path):
                continue
            entry = inspect_source(path, supported, known)
            if entry is None:
                continue
            entry.existing_match = bool(
                normalize(entry.name) in existing_names
                or (entry.product_id and entry.product_id.upper() in existing_products)
            )
            results.setdefault(entry.source_path.lower(), entry)
    return sorted(results.values(), key=lambda item: (item.existing_match, item.name.lower()))


def inspect_source(path: Path, supported: set[str] | None = None, known: dict[str, dict[str, str]] | None = None) -> RomLibraryEntry | None:
    supported = supported if supported is not None else {"GDI", "CDI"}
    known = known if known is not None else _known_metadata()
    path = Path(path)
    if _is_inside_gdemu_menu_slot(path):
        return None
    if path.is_file():
        suffix = path.suffix.lower()
        if suffix == ".gdi" and "GDI" in supported:
            return _entry_from_folder(path.parent, known)
        if suffix == ".cdi" and "CDI" in supported:
            name = _name_from_image_file(path)
            metadata = known.get(normalize(name), {})
            product_id = metadata.get("product", "") or read_disc_product_id_from_image(path)
            return RomLibraryEntry(
                name=name,
                media_type="CDI",
                source_path=str(path),
                product_id=product_id,
                region=metadata.get("region", ""),
                disc=metadata.get("disc", "1/1"),
                vga=metadata.get("vga", "1"),
                version=metadata.get("version", ""),
                date=metadata.get("date", ""),
            )
        return None
    if path.is_dir():
        return _entry_from_folder(path, known)
    return None


def _entry_from_folder(folder: Path, known: dict[str, dict[str, str]]) -> RomLibraryEntry | None:
    if _is_gdemu_menu_slot(folder):
        return None
    media_type = detect_media_type(folder)
    if media_type not in {"GDI", "CDI"}:
        return None
    slot = int(folder.name) if folder.name.isdigit() else 0
    name = resolve_game_display_name(folder, "", slot).name
    metadata = known.get(normalize(name), {})
    product_id = metadata.get("product", "") or read_disc_product_id(folder)
    return RomLibraryEntry(
        name=name,
        media_type=media_type,
        source_path=str(folder),
        product_id=product_id,
        region=metadata.get("region", ""),
        disc=metadata.get("disc", "1/1"),
        vga=metadata.get("vga", "1"),
        version=metadata.get("version", ""),
        date=metadata.get("date", ""),
    )


def _name_from_image_file(path: Path) -> str:
    name_txt = read_name_txt(path.parent)
    if is_descriptive_game_name(name_txt):
        return name_txt
    stem = " ".join(path.stem.replace("_", " ").replace(".", " ").split())
    if is_descriptive_game_name(stem):
        return stem
    internal_name = read_disc_internal_name_from_image(path)
    if is_descriptive_game_name(internal_name):
        return internal_name
    return stem or path.parent.name


def _known_metadata() -> dict[str, dict[str, str]]:
    data = parse_openmenu_ini(DEFAULT_INI)
    result: dict[str, dict[str, str]] = {}
    for item in data.values():
        name = (item.get("name") or "").strip()
        if not name:
            continue
        result.setdefault(normalize(name), item)
    return result


def _is_inside_gdemu_menu_slot(path: Path) -> bool:
    path = Path(path)
    candidates = [path] if path.is_dir() else []
    candidates.extend(path.parents)
    return any(_is_gdemu_menu_slot(candidate) for candidate in candidates)


def is_gdemu_menu_slot(folder: Path) -> bool:
    return _is_gdemu_menu_slot(folder)


def _is_gdemu_menu_slot(folder: Path) -> bool:
    folder = Path(folder)
    if folder.name != "01" or not folder.is_dir():
        return False
    try:
        files = [path.name.lower() for path in folder.iterdir() if path.is_file()]
    except OSError:
        return False
    if any("gdmenu" in name or "openmenu" in name for name in files):
        return True
    if "disc.gdi" in files and any(name.startswith("track05.") for name in files):
        return True
    return False

