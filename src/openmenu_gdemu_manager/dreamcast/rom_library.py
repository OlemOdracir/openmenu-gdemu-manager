from __future__ import annotations

from pathlib import Path

from ..core.matching import normalize
from .metadata import (
    detect_media_type,
    parse_openmenu_ini,
    read_disc_product_id,
    read_disc_product_id_from_image,
    read_name_txt,
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
    if path.is_file():
        suffix = path.suffix.lower()
        if suffix == ".gdi" and "GDI" in supported:
            return _entry_from_folder(path.parent, known)
        if suffix == ".cdi" and "CDI" in supported:
            metadata = known.get(normalize(path.stem), {})
            product_id = metadata.get("product", "") or read_disc_product_id_from_image(path)
            return RomLibraryEntry(
                name=read_name_txt(path.parent) or path.stem,
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
    media_type = detect_media_type(folder)
    if media_type not in {"GDI", "CDI"}:
        return None
    name = read_name_txt(folder) or folder.name
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


def _known_metadata() -> dict[str, dict[str, str]]:
    data = parse_openmenu_ini(DEFAULT_INI)
    result: dict[str, dict[str, str]] = {}
    for item in data.values():
        name = (item.get("name") or "").strip()
        if not name:
            continue
        result.setdefault(normalize(name), item)
    return result

