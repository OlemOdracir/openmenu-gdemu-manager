from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps, ImageStat


NORMALIZED_SIZE = 256
PREVIEW_SIZE = 512
NORMALIZATION_MODE = "contain_square"


@dataclass
class QualityReport:
    label: str
    score: int
    width: int
    height: int
    min_side: int
    aspect_ratio: float
    sharpness: float
    accepted: bool
    warning: str = ""

    @property
    def display(self) -> str:
        return f"{self.label} ({self.width}x{self.height}, score {self.score})"


def apply_quality_report(game, report: QualityReport, normalization_mode: str = "") -> None:
    game.quality_label = report.label
    game.quality_score = report.score
    game.image_width = report.width
    game.image_height = report.height
    game.normalization_mode = normalization_mode


def analyze_image_file(path: Path) -> QualityReport | None:
    try:
        with Image.open(path) as image:
            return analyze_image(image)
    except Exception:
        return None


def analyze_image(image: Image.Image) -> QualityReport:
    rgb = image.convert("RGB")
    width, height = rgb.size
    min_side = min(width, height)
    aspect_ratio = width / max(1, height)
    sharpness = _sharpness(rgb)

    if min_side < 200:
        label = "Rechazar"
        base = 15
        warning = "Resolucion demasiado baja para normalizar a 256x256."
        accepted = False
    elif min_side < 240:
        label = "Baja"
        base = 45
        warning = "Resolucion baja para OpenMenu; se ampliara hasta 256x256."
        accepted = True
    elif min_side < NORMALIZED_SIZE:
        label = "Aceptable"
        base = 75
        warning = "Resolucion cercana al limite de OpenMenu; se ampliara levemente."
        accepted = True
    else:
        label = "Alta"
        base = 100
        warning = ""
        accepted = True

    aspect_penalty = 0
    if aspect_ratio < 0.55 or aspect_ratio > 1.9:
        aspect_penalty = 12
        if not warning:
            warning = "Relacion de aspecto poco usual para caratula."

    blur_penalty = 0
    if sharpness < 8 and min_side >= NORMALIZED_SIZE:
        blur_penalty = 10
        if not warning:
            warning = "La imagen parece blanda o borrosa."

    score = max(0, min(100, base - aspect_penalty - blur_penalty))
    if not accepted:
        score = min(score, 25)

    return QualityReport(
        label=label,
        score=score,
        width=width,
        height=height,
        min_side=min_side,
        aspect_ratio=aspect_ratio,
        sharpness=sharpness,
        accepted=accepted,
        warning=warning,
    )


def normalize_cover(image: Image.Image, size: int = NORMALIZED_SIZE) -> Image.Image:
    rgb = image.convert("RGB")
    contained = ImageOps.contain(rgb, (size, size), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (size, size), (0, 0, 0))
    x = (size - contained.width) // 2
    y = (size - contained.height) // 2
    canvas.paste(contained, (x, y))
    return canvas


def make_preview(image: Image.Image, size: int = PREVIEW_SIZE) -> Image.Image:
    rgb = image.convert("RGB")
    contained = ImageOps.contain(rgb, (size, size), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (size, size), (24, 24, 24))
    x = (size - contained.width) // 2
    y = (size - contained.height) // 2
    canvas.paste(contained, (x, y))
    return canvas


def save_cover_set(image: Image.Image, base_name: str, originals_dir: Path, normalized_dir: Path, preview_dir: Path) -> tuple[Path, Path, Path, QualityReport]:
    originals_dir.mkdir(parents=True, exist_ok=True)
    normalized_dir.mkdir(parents=True, exist_ok=True)
    preview_dir.mkdir(parents=True, exist_ok=True)

    report = analyze_image(image)
    original_path = originals_dir / base_name
    normalized_path = normalized_dir / base_name
    preview_path = preview_dir / base_name

    image.convert("RGB").save(original_path, "PNG")
    normalize_cover(image).save(normalized_path, "PNG")
    make_preview(image).save(preview_path, "PNG")
    return original_path, normalized_path, preview_path, report


def _sharpness(image: Image.Image) -> float:
    gray = image.convert("L").resize((128, 128), Image.Resampling.LANCZOS)
    edges = gray.filter(ImageFilter.FIND_EDGES)
    stat = ImageStat.Stat(edges)
    return float(stat.stddev[0])
