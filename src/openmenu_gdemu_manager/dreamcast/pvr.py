from pathlib import Path

import numpy as np
from PIL import Image


IMG_START = 0x20020
IMG_SIZE = 131104
WIDTH = 256
HEIGHT = 256


def _build_morton_lut() -> np.ndarray:
    y_c = np.repeat(np.arange(HEIGHT, dtype=np.uint32), WIDTH)
    x_c = np.tile(np.arange(WIDTH, dtype=np.uint32), HEIGHT)
    z = np.zeros(WIDTH * HEIGHT, dtype=np.uint32)
    for i in range(8):
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
