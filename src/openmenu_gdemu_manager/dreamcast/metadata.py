import re
from pathlib import Path


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
