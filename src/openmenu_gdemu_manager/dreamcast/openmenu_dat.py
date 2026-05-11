from __future__ import annotations

import math
import re
import struct
from dataclasses import dataclass
from pathlib import Path

from .pvr import image_to_pvr
from .pvr import decode_pvr_bytes


BOX_ENTRY_SIZE = 0x20020
ICON_ENTRY_SIZE = 0x8020
DAT_HEADER_SIZE = 16
DAT_INDEX_SIZE = 16
DAT_NAME_LEN = 10
DAT_MAGIC = b"DAT\x01"


@dataclass
class DatEntry:
    name: str
    data: bytes


def normalize_dat_serial(serial: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]", "", serial or "")
    return normalized[:DAT_NAME_LEN].upper()


def read_dat(path: Path, entry_size: int) -> list[DatEntry]:
    path = Path(path)
    if not path.exists():
        return []
    raw = path.read_bytes()
    if len(raw) < DAT_HEADER_SIZE:
        raise ValueError(f"{path.name} demasiado pequeno para cabecera DAT")
    magic, declared_size, count, _reserved = struct.unpack_from("<4sIII", raw, 0)
    if magic != DAT_MAGIC:
        raise ValueError(f"{path.name} no tiene cabecera DAT valida")
    if declared_size != entry_size:
        raise ValueError(f"{path.name} declara entrada 0x{declared_size:X}, esperado 0x{entry_size:X}")
    index_end = DAT_HEADER_SIZE + count * DAT_INDEX_SIZE
    if len(raw) < index_end:
        raise ValueError(f"{path.name} no contiene indice DAT completo")

    entries: list[DatEntry] = []
    for index in range(count):
        offset = DAT_HEADER_SIZE + index * DAT_INDEX_SIZE
        name_raw = raw[offset:offset + DAT_NAME_LEN]
        name = name_raw.split(b"\x00", 1)[0].decode("ascii", errors="ignore").strip()
        file_number = struct.unpack_from("<I", raw, offset + 12)[0]
        data_offset = entry_size * file_number
        data_end = data_offset + entry_size
        if data_end > len(raw):
            raise ValueError(f"{path.name} tiene entrada {name or index} fuera del archivo")
        if name:
            entries.append(DatEntry(name=name, data=raw[data_offset:data_end]))
    return entries


def read_dat_by_name(path: Path, entry_size: int) -> dict[str, DatEntry]:
    return {entry.name.upper(): entry for entry in read_dat(path, entry_size)}


def extract_dat_cover(entries: dict[str, DatEntry], serial: str, out_path: Path) -> Path | None:
    normalized = normalize_dat_serial(serial)
    if not normalized:
        return None
    entry = entries.get(normalized)
    if entry is None:
        return None
    try:
        image = decode_pvr_bytes(entry.data)
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(out_path, "PNG")
        return out_path
    except Exception:
        return None


def write_dat(path: Path, entry_size: int, entries: list[DatEntry]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized_entries = _dedupe_entries(entries)
    index_size = DAT_HEADER_SIZE + len(normalized_entries) * DAT_INDEX_SIZE
    starting_file_number = max(1, math.ceil(index_size / entry_size))
    with path.open("wb") as handle:
        handle.write(struct.pack("<4sIII", DAT_MAGIC, entry_size, len(normalized_entries), 0))
        for index, entry in enumerate(normalized_entries):
            file_number = starting_file_number + index
            name = normalize_dat_serial(entry.name).encode("ascii")
            handle.write(name.ljust(DAT_NAME_LEN, b"\x00")[:DAT_NAME_LEN])
            handle.write(struct.pack("<HI", 0, file_number))
        first_data_offset = entry_size * starting_file_number
        if handle.tell() < first_data_offset:
            handle.write(b"\x00" * (first_data_offset - handle.tell()))
        for index, entry in enumerate(normalized_entries):
            file_number = starting_file_number + index
            handle.seek(entry_size * file_number)
            data = entry.data
            if len(data) != entry_size:
                raise ValueError(f"Entrada {entry.name} mide {len(data)}, esperado {entry_size}")
            handle.write(data)


def update_artwork_dats(data_dir: Path, updates: dict[str, Path]) -> int:
    data_dir = Path(data_dir)
    box_path = data_dir / "BOX.DAT"
    icon_path = data_dir / "ICON.DAT"
    box_entries = read_dat(box_path, BOX_ENTRY_SIZE)
    icon_entries = read_dat(icon_path, ICON_ENTRY_SIZE)
    box_by_name = {entry.name.upper(): entry for entry in box_entries}
    icon_by_name = {entry.name.upper(): entry for entry in icon_entries}

    changed = 0
    for raw_serial, image_path in updates.items():
        serial = normalize_dat_serial(raw_serial)
        if not serial:
            continue
        image_path = Path(image_path)
        if not image_path.exists():
            continue
        box_by_name[serial] = DatEntry(serial, image_to_pvr(image_path, 256, 256))
        icon_by_name[serial] = DatEntry(serial, image_to_pvr(image_path, 128, 128))
        changed += 1

    if changed:
        write_dat(box_path, BOX_ENTRY_SIZE, list(box_by_name.values()))
        write_dat(icon_path, ICON_ENTRY_SIZE, list(icon_by_name.values()))
    return changed


def _dedupe_entries(entries: list[DatEntry]) -> list[DatEntry]:
    by_name: dict[str, DatEntry] = {}
    for entry in entries:
        name = normalize_dat_serial(entry.name)
        if name:
            by_name[name] = DatEntry(name, entry.data)
    return [by_name[name] for name in sorted(by_name)]
