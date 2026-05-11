from pathlib import Path
import struct

import numpy as np
from PIL import Image


IMG_START = 0x20020
IMG_SIZE = 131104
WIDTH = 256
HEIGHT = 256
GBIX_SIZE = 8
GBIX_GBIX_VALUE = 0
GBIX_PAD = b"\x20\x20\x20\x20"
PX_FORMAT_RGB565 = 0x01
DATA_TYPE_TWIDDLED = 0x01


def _build_morton_lut(width: int = WIDTH, height: int = HEIGHT) -> np.ndarray:
    y_c = np.repeat(np.arange(height, dtype=np.uint32), width)
    x_c = np.tile(np.arange(width, dtype=np.uint32), height)
    z = np.zeros(width * height, dtype=np.uint32)
    bits = width.bit_length() - 1
    for i in range(bits):
        z |= ((y_c >> i) & 1) << (2 * i)
        z |= ((x_c >> i) & 1) << (2 * i + 1)
    return z


_MORTON_LUT = _build_morton_lut()


def decode_pvr_bytes(pvr: bytes) -> Image.Image:
    if len(pvr) < IMG_SIZE:
        raise ValueError("PVR data is too short")
    if pvr[:4] != b"GBIX" or pvr[16:20] != b"PVRT":
        raise ValueError("Unsupported PVR header")

    raw = np.frombuffer(pvr[32:32 + WIDTH * HEIGHT * 2], dtype=np.uint16)
    vals = raw[_MORTON_LUT]
    r = ((vals >> 11) & 0x1F) * 255 // 31
    g = ((vals >> 5) & 0x3F) * 255 // 63
    b = (vals & 0x1F) * 255 // 31
    pixels = np.stack([r, g, b], axis=1).reshape(HEIGHT, WIDTH, 3).astype(np.uint8)
    return Image.fromarray(pixels, "RGB")


def extract_cover_from_track(track_path: Path, index: int, out_path: Path) -> Path | None:
    if index is None or not track_path.exists():
        return None
    offset = IMG_START + index * IMG_SIZE
    try:
        with open(track_path, "rb") as handle:
            handle.seek(offset)
            pvr = handle.read(IMG_SIZE)
        image = decode_pvr_bytes(pvr)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(out_path, "PNG")
        return out_path
    except Exception:
        return None


def image_to_pvr(image_path: Path, width: int, height: int) -> bytes:
    image = Image.open(image_path).convert("RGB")
    image = image.resize((width, height), Image.Resampling.LANCZOS)
    bits = width.bit_length() - 1
    pixel_data = bytearray(width * height * 2)
    for y in range(height):
        for x in range(width):
            r, g, b = image.getpixel((x, y))
            rgb565 = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
            z = _xy_to_morton(x, y, bits)
            struct.pack_into("<H", pixel_data, z * 2, rgb565)
    pvrt_data_size = 8 + (width * height * 2)
    header = (
        b"GBIX"
        + struct.pack("<I", GBIX_SIZE)
        + struct.pack("<I", GBIX_GBIX_VALUE)
        + GBIX_PAD
        + b"PVRT"
        + struct.pack("<I", pvrt_data_size)
        + struct.pack("<BB", PX_FORMAT_RGB565, DATA_TYPE_TWIDDLED)
        + b"\x00\x00"
        + struct.pack("<HH", width, height)
    )
    return header + bytes(pixel_data)


def _xy_to_morton(x: int, y: int, bits: int) -> int:
    z = 0
    for i in range(bits):
        z |= ((y >> i) & 1) << (2 * i)
        z |= ((x >> i) & 1) << (2 * i + 1)
    return z
