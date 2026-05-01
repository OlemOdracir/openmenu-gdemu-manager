from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from ..config.paths import MANAGER_CACHE_DIR


PLACEHOLDER_PATH = MANAGER_CACHE_DIR / "assets" / "no_cover_v2.png"


def ensure_no_cover_asset(path: Path = PLACEHOLDER_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return path

    image = Image.new("RGB", (512, 512), "#b91c1c")
    draw = ImageDraw.Draw(image)
    draw.rectangle((18, 18, 494, 494), outline="#7f1d1d", width=12)
    draw.rectangle((42, 42, 470, 470), outline="#fecaca", width=4)

    font_no = _font(118)
    font_cover = _font(76)
    font_note = _font(27)
    _center_text(draw, (0, 115, 512, 225), "NO", font_no, "#ffffff")
    _center_text(draw, (0, 228, 512, 320), "COVER", font_cover, "#ffffff")
    _center_text(draw, (0, 355, 512, 400), "FALTA CARATULA", font_note, "#fee2e2")

    draw.line((96, 334, 416, 334), fill="#fee2e2", width=5)
    image.save(path, "PNG")
    return path


def _font(size: int):
    for name in ("arialbd.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _center_text(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], text: str, font, fill: str) -> None:
    left, top, right, bottom = box
    bbox = draw.textbbox((0, 0), text, font=font)
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    x = left + ((right - left - width) // 2)
    y = top + ((bottom - top - height) // 2) - bbox[1]
    draw.text((x, y), text, fill=fill, font=font)

