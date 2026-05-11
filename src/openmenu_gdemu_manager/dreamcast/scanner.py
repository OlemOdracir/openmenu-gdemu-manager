import re
import logging
from pathlib import Path

from .metadata import (
    artwork_serial_candidates,
    detect_media_type,
    find_openmenu_track,
    menu_product_id_for_slot,
    parse_openmenu_from_track,
    parse_openmenu_ini,
    read_disc_product_id,
    read_name_txt,
)
from .openmenu_dat import BOX_ENTRY_SIZE, DatEntry, extract_dat_cover, read_dat_by_name
from ..core.image_quality import analyze_image_file, apply_quality_report
from ..core.models import GameItem
from ..config.paths import AUDIT_DIR, DEFAULT_INI, MANAGER_CACHE_DIR
from ..config.settings import configured_buildgdi_path, load_settings
from .pvr import extract_cover_from_track
from ..config.state import apply_state
from ..services.openmenu_rebuilder import _run_buildgdi


log = logging.getLogger(__name__)


def load_cover_index_map(audit_dir: Path = AUDIT_DIR) -> tuple[dict[int, int], dict[str, int]]:
    slot_map: dict[int, int] = {}
    product_map: dict[str, int] = {}
    if not audit_dir.exists():
        return slot_map, product_map
    for path in audit_dir.glob("slot*_idx*_*.png"):
        match = re.match(r"^slot(\d+)_idx(\d+)_([^_]+)_.*\.png$", path.name)
        if not match:
            continue
        slot, idx, product = match.groups()
        slot_map[int(slot)] = int(idx)
        product_map.setdefault(product.upper(), int(idx))
    return slot_map, product_map


def scan_sd_root(root: Path, state: dict | None = None, ini_path: Path = DEFAULT_INI) -> list[GameItem]:
    root = Path(root)
    log.info("Scanning root: %s", root)
    slot_map, product_map = load_cover_index_map()
    track_path = find_openmenu_track(root)
    metadata = _load_menu_metadata(root, track_path, ini_path)
    box_entries = _load_openmenu_box_entries(root, track_path)
    physical_slots = _physical_game_slots(root)
    consistency = analyze_menu_consistency(physical_slots, metadata)
    games: list[GameItem] = []

    if not root.exists():
        log.warning("Root does not exist: %s", root)
        return games

    for folder in sorted([p for p in root.iterdir() if p.is_dir() and p.name.isdigit()], key=lambda p: int(p.name)):
        slot = int(folder.name)
        if slot == 1:
            continue
        meta = metadata.get(slot, {})
        name = read_name_txt(folder) or meta.get("name", "") or folder.name
        raw_product_id = meta.get("product", "")
        disc_product_id = read_disc_product_id(folder)
        product_id = menu_product_id_for_slot(slot, raw_product_id, disc_product_id)
        artwork_serials = artwork_serial_candidates(slot, raw_product_id, product_id, disc_product_id)
        cover_index = slot_map.get(slot)
        if cover_index is None:
            for serial in artwork_serials:
                cover_index = product_map.get(serial.upper())
                if cover_index is not None:
                    break

        current_cover = None
        if box_entries:
            for serial in artwork_serials or [f"SLOT{slot:03d}"]:
                out_path = MANAGER_CACHE_DIR / "current" / root_fingerprint(root) / f"slot{slot:03d}_{serial}_box.png"
                current_cover = extract_dat_cover(box_entries, serial, out_path)
                if current_cover is not None:
                    break

        if current_cover is None and cover_index is not None and track_path.exists():
            out_path = MANAGER_CACHE_DIR / "current" / root_fingerprint(root) / f"slot{slot:03d}_idx{cover_index:03d}.png"
            current_cover = extract_cover_from_track(track_path, cover_index, out_path)
            if current_cover is None:
                log.warning("Could not extract cover for slot %03d idx %s", slot, cover_index)

        game = GameItem(
            slot=slot,
            name=name,
            product_id=product_id,
            region=meta.get("region", ""),
            disc=meta.get("disc", ""),
            vga=meta.get("vga", ""),
            version=meta.get("version", ""),
            date=meta.get("date", ""),
            media_type=detect_media_type(folder),
            folder=folder,
            cover_index=cover_index,
            current_cover=current_cover,
            status="no_revisada" if current_cover else "faltante",
            save_status="pendiente_guardar" if product_id != raw_product_id else "",
            artwork_serials=artwork_serials,
            previous_product_id=raw_product_id if product_id != raw_product_id else "",
            consistency_warnings=consistency.get(slot, []),
        )
        if game.consistency_warnings and not game.save_status:
            game.save_status = "pendiente_guardar"
        if current_cover is not None:
            report = analyze_image_file(current_cover)
            if report is not None:
                apply_quality_report(game, report, "openmenu_current")
        if state is not None:
            apply_state(game, state, root)
        games.append(game)
    log.info("Scan finished: %s games from %s", len(games), root)
    return games


def analyze_menu_consistency(physical_slots: set[int], metadata: dict[int, dict[str, str]]) -> dict[int, list[str]]:
    menu_slots = {slot for slot in metadata if slot != 1}
    warnings: dict[int, list[str]] = {}
    if not physical_slots:
        return warnings

    for slot in sorted(physical_slots - menu_slots):
        warnings.setdefault(slot, []).append("folder_without_menu_entry")
    for slot in sorted(menu_slots - physical_slots):
        if slot > 1:
            warnings.setdefault(slot, []).append("menu_entry_without_folder")

    expected = set(range(2, max(physical_slots) + 1))
    for slot in sorted(expected - physical_slots):
        warnings.setdefault(slot, []).append("missing_physical_slot")
        for higher_slot in sorted(physical_slots):
            if higher_slot > slot:
                warnings.setdefault(higher_slot, []).append("slot_compaction_needed")
        break
    return warnings


def _physical_game_slots(root: Path) -> set[int]:
    if not root.exists():
        return set()
    return {int(path.name) for path in root.iterdir() if path.is_dir() and path.name.isdigit() and int(path.name) != 1}


def root_fingerprint(root: Path) -> str:
    text = str(root.resolve()).replace("\\", "_").replace(":", "")
    return re.sub(r"[^A-Za-z0-9_]+", "_", text).strip("_") or "root"


def _load_menu_metadata(root: Path, track_path: Path, ini_path: Path) -> dict[int, dict[str, str]]:
    metadata: dict[int, dict[str, str]] = {}
    for source in (ini_path, root / "OPENMENU.current.generated.ini"):
        metadata.update(parse_openmenu_ini(source))
    embedded = parse_openmenu_from_track(track_path)
    if embedded:
        metadata.update(embedded)
        log.info("Loaded %s menu metadata entries from %s", len(embedded), track_path)
    elif metadata:
        log.info("Loaded %s menu metadata entries from INI files", len(metadata))
    else:
        log.info("No OpenMenu metadata found for %s", root)
    return metadata


def _load_openmenu_box_entries(root: Path, track_path: Path) -> dict[str, DatEntry]:
    data_dir = _extract_openmenu_data_dir(root, track_path)
    if data_dir is None:
        return {}
    box_path = data_dir / "BOX.DAT"
    if not box_path.exists():
        return {}
    try:
        entries = read_dat_by_name(box_path, BOX_ENTRY_SIZE)
        log.info("Loaded %s BOX.DAT entries from %s", len(entries), box_path)
        return entries
    except Exception:
        log.exception("Could not read BOX.DAT from %s", box_path)
        return {}


def _extract_openmenu_data_dir(root: Path, track_path: Path) -> Path | None:
    gdi_path = Path(root) / "01" / "disc.gdi"
    if not gdi_path.exists():
        return None
    data_dir = MANAGER_CACHE_DIR / "current" / root_fingerprint(root) / "openmenu_data"
    box_path = data_dir / "BOX.DAT"
    if _cache_is_current(box_path, track_path):
        return data_dir

    buildgdi = configured_buildgdi_path(load_settings())
    if not buildgdi.is_file():
        log.warning("buildgdi.exe not found; cannot extract current BOX.DAT: %s", buildgdi)
        return data_dir if box_path.exists() else None

    data_dir.mkdir(parents=True, exist_ok=True)
    result = _run_buildgdi(
        [
            str(buildgdi),
            "-extract",
            "-gdi", str(gdi_path),
            "-output", str(data_dir),
            "-ip", str(data_dir / "IP.BIN"),
        ],
        cwd=gdi_path.parent,
    )
    if result.returncode != 0 and not box_path.exists():
        output = "\n".join(part for part in (result.stdout, result.stderr) if part)
        log.warning("buildgdi could not extract BOX.DAT from %s: %s", gdi_path, output[:1000])
        return None
    if box_path.exists():
        return data_dir
    return None


def _cache_is_current(cache_path: Path, source_path: Path) -> bool:
    try:
        return cache_path.exists() and source_path.exists() and cache_path.stat().st_mtime >= source_path.stat().st_mtime
    except OSError:
        return False

