from pathlib import Path

from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap


def pil_to_pixmap(image: Image.Image, max_size: tuple[int, int]) -> QPixmap:
    copy = image.convert("RGBA")
    copy.thumbnail(max_size, Image.Resampling.LANCZOS)
    data = copy.tobytes("raw", "RGBA")
    qimage = QImage(data, copy.width, copy.height, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(qimage.copy())


def file_to_pixmap(path: Path | str, max_size: tuple[int, int]) -> QPixmap:
    image = Image.open(path).convert("RGBA")
    return pil_to_pixmap(image, max_size)


def fit_pixmap(pixmap: QPixmap, width: int, height: int) -> QPixmap:
    return pixmap.scaled(width, height, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
