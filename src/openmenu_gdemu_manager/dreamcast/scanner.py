import re
import logging
from pathlib import Path

from .metadata import detect_media_type, parse_openmenu_from_track, parse_openmenu_ini, read_name_txt
from ..core.image_quality import analyze_image_file, apply_quality_report
from ..core.models import GameItem
from ..config.paths import AUDIT_DIR, DEFAULT_INI, MANAGER_CACHE_DIR
from .pvr import extract_cover_from_track
from ..config.state import apply_state


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
    track_path = root / "01" / "track05.iso"
    metadata = _load_menu_metadata(root, track_path, ini_path)
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
        product_id = meta.get("product", "")
        cover_index = slot_map.get(slot)
        if cover_index is None and product_id:
            cover_index = product_map.get(product_id.upper())

        current_cover = None
        if cover_index is not None and track_path.exists():
            out_path = MANAGER_CACHE_DIR / "current" / root_fingerprint(root) / f"slot{slot:03d}_idx{cover_index:03d}.png"
            current_cover = extract_cover_from_track(track_path, cover_index, out_path)
            if current_cover is None:
                log.warning("Could not extract cover for slot %03d idx %s", slot, cover_index)
        elif slot in slot_map:
            current_cover = None

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
        )
        if current_cover is not None:
            report = analyze_image_file(current_cover)
            if report is not None:
                apply_quality_report(game, report, "openmenu_current")
        if state is not None:
            apply_state(game, state, root)
        games.append(game)
    log.info("Scan finished: %s games from %s", len(games), root)
    return games


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

