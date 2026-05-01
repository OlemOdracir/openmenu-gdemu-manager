from __future__ import annotations

from pathlib import Path

import re

from PySide6.QtCore import QRect
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QWidget

from ..theme import ThemePackage, template_palette


class ThemeBackgroundWidget(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("MainRoot")
        self._background_path: Path | None = None
        self._pixmap = QPixmap()
        self._opacity = 0.0
        self._overlay = ""

    def apply_theme_background(self, theme: ThemePackage, enabled: bool = True) -> None:
        background = theme.background or {}
        path = theme.background_path() if enabled else None
        self._background_path = path
        self._pixmap = QPixmap(str(path)) if path else QPixmap()
        try:
            self._opacity = max(0.0, min(1.0, float(background.get("opacity", 0.22))))
        except (TypeError, ValueError):
            self._opacity = 0.22
        self._overlay = str(theme.palette.get("background_overlay") or template_palette(theme.id).get("window_bg"))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        if not self._pixmap.isNull():
            target = self.rect()
            source = _cover_source_rect(self._pixmap, target)
            painter.setOpacity(self._opacity)
            painter.drawPixmap(target, self._pixmap, source)
            painter.setOpacity(1.0)
        overlay = _parse_color(self._overlay)
        if overlay.isValid():
            painter.fillRect(self.rect(), overlay)
        painter.end()
        super().paintEvent(event)


def _cover_source_rect(pixmap: QPixmap, target: QRect) -> QRect:
    if target.width() <= 0 or target.height() <= 0:
        return pixmap.rect()
    source = pixmap.rect()
    target_ratio = target.width() / target.height()
    source_ratio = source.width() / source.height()
    if source_ratio > target_ratio:
        new_width = int(source.height() * target_ratio)
        x = source.x() + (source.width() - new_width) // 2
        return QRect(x, source.y(), new_width, source.height())
    new_height = int(source.width() / target_ratio)
    y = source.y() + (source.height() - new_height) // 2
    return QRect(source.x(), y, source.width(), new_height)


def _parse_color(value: str) -> QColor:
    color = QColor(value)
    if color.isValid():
        return color
    match = re.fullmatch(r"rgba\((\d+),\s*(\d+),\s*(\d+),\s*([0-9.]+)\)", value.strip())
    if not match:
        return QColor()
    red, green, blue = (max(0, min(255, int(match.group(i)))) for i in range(1, 4))
    raw_alpha = float(match.group(4))
    alpha = int(raw_alpha * 255) if raw_alpha <= 1 else int(raw_alpha)
    return QColor(red, green, blue, max(0, min(255, alpha)))
