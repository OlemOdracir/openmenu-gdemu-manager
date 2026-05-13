import re
from functools import lru_cache
from pathlib import Path

IP_BIN_MAGIC = b"SEGA SEGAKATANA"
IP_BIN_HEADER_SIZE = 0x100
IP_BIN_SEARCH_LIMIT = 8 * 1024 * 1024


def parse_openmenu_ini(path: Path) -> dict[int, dict[str, str]]:
    if not path.exists():
        return {}
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    return parse_openmenu_text(text)


def parse_openmenu_text(text: str) -> dict[int, dict[str, str]]:
    items: dict[int, dict[str, str]] = {}
    for line in text.splitlines():
        match = re.match(r"^(\d+)\.(\w+)=(.*)$", line.strip())
        if not match:
            continue
        slot, key, value = match.groups()
        items.setdefault(int(slot), {})[key] = value
    return items


def parse_openmenu_from_track(track_path: Path) -> dict[int, dict[str, str]]:
    track_path = Path(track_path)
    if not track_path.exists():
        return {}
    try:
        data = track_path.read_bytes()
    except OSError:
        return {}
    start = data.find(b"[OPENMENU]")
    if start == -1:
        return {}
    end = data.find(b"\x00" * 64, start)
    if end == -1:
        end = min(len(data), start + 64 * 1024)
    text = data[start:end].decode("latin-1", errors="replace")
    return parse_openmenu_text(text)


def find_openmenu_track(root: Path) -> Path:
    slot1 = Path(root) / "01"
    preferred = slot1 / "track05.iso"
    if preferred.exists():
        return preferred
    gdi = slot1 / "disc.gdi"
    if gdi.exists():
        declared = _declared_data_tracks(gdi)
        for name in reversed(declared):
            candidate = slot1 / name
            if candidate.exists():
                return candidate
    return preferred


def read_disc_product_id(folder: Path | None) -> str:
    return _read_first_disc_header_field(folder, _read_ip_bin_product)


def read_disc_product_id_from_image(path: Path | None) -> str:
    if path is None:
        return ""
    return _read_ip_bin_product(Path(path))


def read_disc_internal_name(folder: Path | None) -> str:
    return _read_first_disc_header_field(folder, _read_ip_bin_internal_name)


def _read_first_disc_header_field(folder: Path | None, reader) -> str:
    if folder is None:
        return ""
    folder = Path(folder)
    if not folder.exists():
        return ""
    candidates: list[Path] = []
    gdi = folder / "disc.gdi"
    if gdi.exists():
        candidates.extend(_gdi_data_tracks(folder, gdi))
    candidates.extend(sorted(folder.glob("*.iso")))
    candidates.extend(sorted(folder.glob("*.bin")))
    candidates.extend(sorted(folder.glob("*.cdi")))
    for candidate in candidates:
        value = reader(candidate)
        if value:
            return value
    return ""


def is_synthetic_slot_serial(serial: str | None) -> bool:
    return bool(re.fullmatch(r"SLOT\d{1,3}", (serial or "").strip().upper()))


def menu_product_id_for_slot(slot: int, raw_product_id: str, disc_product_id: str = "") -> str:
    raw_product_id = (raw_product_id or "").strip()
    disc_product_id = (disc_product_id or "").strip()
    if is_synthetic_slot_serial(raw_product_id) or not raw_product_id:
        return disc_product_id or f"SLOT{slot:03d}"
    return raw_product_id


def artwork_serial_candidates(slot: int, raw_product_id: str, menu_product_id: str, disc_product_id: str = "") -> list[str]:
    candidates: list[str] = []
    for serial in (
        raw_product_id,
        menu_product_id,
        f"SLOT{slot:03d}" if is_synthetic_slot_serial(raw_product_id) or not raw_product_id else "",
        disc_product_id,
    ):
        normalized = _normalize_serial(serial)
        if normalized and normalized not in candidates:
            candidates.append(normalized)
    return candidates


def _declared_data_tracks(gdi_path: Path) -> list[str]:
    try:
        lines = gdi_path.read_text(encoding="ascii", errors="replace").splitlines()
    except OSError:
        return []
    tracks: list[str] = []
    for line in lines[1:]:
        parts = line.split()
        if len(parts) >= 5 and parts[3] == "2048" and parts[4].lower().endswith((".iso", ".bin")):
            tracks.append(parts[4])
    return tracks


def _gdi_data_tracks(folder: Path, gdi_path: Path) -> list[Path]:
    return [folder / name for name in _declared_data_tracks(gdi_path)]


def _read_ip_bin_product(track_path: Path) -> str:
    header = _read_ip_bin_header(track_path, 0x60)
    if len(header) < 0x50:
        return ""
    return header[0x40:0x4A].decode("ascii", errors="ignore").strip().replace("-", "")


def _read_ip_bin_internal_name(track_path: Path) -> str:
    header = _read_ip_bin_header(track_path, 0x100)
    if len(header) < 0x100:
        return ""
    return " ".join(header[0x80:0x100].decode("ascii", errors="ignore").split())


def _read_ip_bin_header(track_path: Path, size: int) -> bytes:
    track_path = Path(track_path)
    try:
        stat = track_path.stat()
    except OSError:
        return b""
    header = _read_ip_bin_header_cached(str(track_path), stat.st_mtime_ns, stat.st_size)
    if len(header) < size:
        return b""
    return header[:size]


@lru_cache(maxsize=512)
def _read_ip_bin_header_cached(path: str, mtime_ns: int, file_size: int) -> bytes:
    del mtime_ns
    read_size = min(max(IP_BIN_HEADER_SIZE, file_size), IP_BIN_SEARCH_LIMIT)
    try:
        with Path(path).open("rb") as handle:
            data = handle.read(read_size)
    except OSError:
        return b""
    start = data.find(IP_BIN_MAGIC)
    if start < 0:
        return b""
    return data[start:start + IP_BIN_HEADER_SIZE]


def _normalize_serial(serial: str | None) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]", "", serial or "")
    return normalized[:10].upper()


def read_name_txt(folder: Path) -> str:
    name_path = folder / "name.txt"
    if not name_path.exists():
        return ""
    try:
        return name_path.read_text(encoding="utf-8-sig", errors="replace").strip().lstrip("\ufeff")
    except OSError:
        return ""


def detect_media_type(folder: Path) -> str:
    if (folder / "disc.gdi").exists():
        return "GDI"
    if (folder / "disc.cdi").exists():
        return "CDI"
    for path in folder.iterdir():
        if path.suffix.lower() == ".gdi":
            return "GDI"
        if path.suffix.lower() == ".cdi":
            return "CDI"
    return ""
