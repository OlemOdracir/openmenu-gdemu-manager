from __future__ import annotations

import ctypes
import shutil
import struct
from pathlib import Path
from typing import Callable

from ..core.matching import normalize
from .pvr import image_to_pvr
from .metadata import parse_openmenu_ini
from ..core.models import GameItem
from ..config.paths import DEFAULT_INI


IMG_START = 0x20020
IMG_SIZE = 131104
GBIX_SIZE = 8
GBIX_GBIX_VALUE = 0
GBIX_PAD = b"\x20\x20\x20\x20"
PVRT_DATA_SIZE = 131080
PX_FORMAT = 0x01
DATA_TYPE = 0x01
WIDTH = HEIGHT = 256
MAX_USER_SLOT = 127
DEFAULT_MENU_ENTRY = {
    "name": "openMenu",
    "disc": "1/1",
    "vga": "1",
    "region": "JUE",
    "version": "V0.1.4",
    "date": "20210609",
    "product": "NEODC_1",
}


def first_free_slot(games: list[GameItem], max_slot: int = MAX_USER_SLOT) -> int | None:
    used = {game.slot for game in games if not game.pending_delete}
    for slot in range(2, max_slot + 1):
        if slot not in used:
            return slot
    return None


CopyProgress = Callable[[str, int, int], None]


def copy_game_source(source_path: Path, destination: Path, progress: CopyProgress | None = None) -> None:
    source_path = Path(source_path)
    if destination.exists():
        raise FileExistsError(f"El slot destino ya existe: {destination}")
    if source_path.is_dir():
        _copytree_with_progress(source_path, destination, progress)
        return
    destination.mkdir(parents=True, exist_ok=True)
    _copy_file_with_progress(source_path, destination / source_path.name, progress, source_path.stat().st_size)


def write_name_txt(folder: Path, title: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "name.txt").write_text(title.strip() + "\n", encoding="utf-8")


def source_size(source_path: Path) -> int:
    source_path = Path(source_path)
    if source_path.is_file():
        return source_path.stat().st_size
    total = 0
    for path in source_path.rglob("*"):
        if path.is_file():
            try:
                total += path.stat().st_size
            except OSError:
                pass
    return total


def _copytree_with_progress(source: Path, destination: Path, progress: CopyProgress | None) -> None:
    total = source_size(source)
    copied = 0
    destination.mkdir(parents=True, exist_ok=False)
    for item in source.rglob("*"):
        relative = item.relative_to(source)
        target = destination / relative
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        copied = _copy_file_with_progress(item, target, progress, total, copied)


def _copy_file_with_progress(source: Path, destination: Path, progress: CopyProgress | None,
                             total: int, copied_before: int = 0) -> int:
    chunk_size = 1024 * 1024
    copied = copied_before
    with source.open("rb") as src, destination.open("wb") as dst:
        while True:
            chunk = src.read(chunk_size)
            if not chunk:
                break
            dst.write(chunk)
            copied += len(chunk)
            if progress:
                progress(source.name, copied, total)
    shutil.copystat(source, destination)
    return copied


def send_to_recycle_bin(path: Path) -> None:
    path = Path(path)
    if not path.exists():
        return

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [
            ("hwnd", ctypes.c_void_p),
            ("wFunc", ctypes.c_uint),
            ("pFrom", ctypes.c_wchar_p),
            ("pTo", ctypes.c_wchar_p),
            ("fFlags", ctypes.c_ushort),
            ("fAnyOperationsAborted", ctypes.c_int),
            ("hNameMappings", ctypes.c_void_p),
            ("lpszProgressTitle", ctypes.c_wchar_p),
        ]

    FO_DELETE = 3
    FOF_SILENT = 0x0004
    FOF_NOCONFIRMATION = 0x0010
    FOF_ALLOWUNDO = 0x0040
    FOF_NOERRORUI = 0x0400

    operation = SHFILEOPSTRUCTW()
    operation.wFunc = FO_DELETE
    operation.pFrom = str(path) + "\0\0"
    operation.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_NOERRORUI | FOF_SILENT
    result = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(operation))
    if result != 0:
        raise OSError(f"No se pudo enviar a la papelera: {path} (codigo {result})")


def write_openmenu_ini(games: list[GameItem], path: Path = DEFAULT_INI) -> str:
    text = build_openmenu_text(games, newline="\r\n")
    path.write_text(text, encoding="utf-8")
    return text


def build_openmenu_text(games: list[GameItem], newline: str = "\r\n") -> str:
    lines = ["[OPENMENU]", f"num_items={len([g for g in games if not g.pending_delete])}", "[ITEMS]"]
    slot1 = _slot1_entry()
    lines.extend(_item_lines(1, slot1))
    for game in sorted([g for g in games if not g.pending_delete], key=lambda item: item.slot):
        lines.extend(_item_lines(game.slot, _item_dict(game)))
    return newline.join(lines) + newline


def patch_track05_menu(track_path: Path, games: list[GameItem]) -> None:
    track_path = Path(track_path)
    if not track_path.exists():
        return
    block, start, original_span = _track05_menu_block(track_path, games)
    if len(block) > original_span:
        raise ValueError(_menu_capacity_error(len(block), original_span))
    data = track_path.read_bytes()
    padded = block + (b"\x00" * (original_span - len(block)))
    with track_path.open("r+b") as handle:
        handle.seek(start)
        handle.write(padded)


def validate_track05_menu_capacity(track_path: Path, games: list[GameItem]) -> None:
    track_path = Path(track_path)
    if not track_path.exists():
        return
    block, _start, original_span = _track05_menu_block(track_path, games)
    if len(block) > original_span:
        raise ValueError(_menu_capacity_error(len(block), original_span))


def _track05_menu_block(track_path: Path, games: list[GameItem]) -> tuple[bytes, int, int]:
    data = track_path.read_bytes()
    start = data.find(b"[OPENMENU]")
    if start == -1:
        raise ValueError("No se encontro bloque [OPENMENU] en track05.iso")
    end = data.find(b"\x00" * 64, start)
    if end == -1:
        raise ValueError("No se encontro el final del bloque del menu en track05.iso")
    original_span = end - start
    block = build_openmenu_text(games, newline="\n").encode("latin-1", errors="replace")
    return block, start, original_span


def _menu_capacity_error(used: int, available: int) -> str:
    over = max(0, used - available)
    return (
        "El bloque del menu excede el espacio disponible "
        f"({used / 1024:.1f} KB usados > {available / 1024:.1f} KB disponibles; "
        f"faltan {over / 1024:.1f} KB). "
        f"Detalle tecnico: {used} > {available} bytes."
    )


def patch_track05_cover(track_path: Path, cover_index: int, image_path: Path) -> None:
    if cover_index is None:
        raise ValueError("Cover index vacio")
    pvr = png_to_pvr(Path(image_path))
    with Path(track_path).open("r+b") as handle:
        handle.seek(IMG_START + (cover_index * IMG_SIZE))
        handle.write(pvr)


def png_to_pvr(png_path: Path) -> bytes:
    return image_to_pvr(png_path, WIDTH, HEIGHT)


def xy_to_morton(x: int, y: int, bits: int) -> int:
    z = 0
    for i in range(bits):
        z |= ((y >> i) & 1) << (2 * i)
        z |= ((x >> i) & 1) << (2 * i + 1)
    return z


def _slot1_entry() -> dict[str, str]:
    slot1 = parse_openmenu_ini(DEFAULT_INI).get(1, {})
    return {
        "name": slot1.get("name", DEFAULT_MENU_ENTRY["name"]),
        "disc": slot1.get("disc", DEFAULT_MENU_ENTRY["disc"]),
        "vga": slot1.get("vga", DEFAULT_MENU_ENTRY["vga"]),
        "region": slot1.get("region", DEFAULT_MENU_ENTRY["region"]),
        "version": slot1.get("version", DEFAULT_MENU_ENTRY["version"]),
        "date": slot1.get("date", DEFAULT_MENU_ENTRY["date"]),
        "product": slot1.get("product", DEFAULT_MENU_ENTRY["product"]),
    }


def _item_lines(slot: int, item: dict[str, str]) -> list[str]:
    key = f"{slot:02d}"
    return [
        f"{key}.name={item['name']}",
        f"{key}.disc={item['disc']}",
        f"{key}.vga={item['vga']}",
        f"{key}.region={item['region']}",
        f"{key}.version={item['version']}",
        f"{key}.date={item['date']}",
        f"{key}.product={item['product']}",
    ]


def _item_dict(game: GameItem) -> dict[str, str]:
    return {
        "name": game.name,
        "disc": game.disc or "1/1",
        "vga": game.vga or "1",
        "region": game.region or "U",
        "version": game.version or "V1.000",
        "date": game.date or "00000000",
        "product": game.product_id or f"SLOT{game.slot:03d}",
    }

