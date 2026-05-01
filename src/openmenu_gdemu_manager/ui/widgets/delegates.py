from __future__ import annotations

import logging

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QStyle,
    QStyledItemDelegate,
)

from ..theme import template_palette

log = logging.getLogger(__name__)

class CoverDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        return QSize(118, 104)

    def paint(self, painter, option, index):
        style = option.widget.style() if option.widget else QApplication.style()
        style.drawPrimitive(QStyle.PrimitiveElement.PE_PanelItemViewItem, option, painter, option.widget)
        pixmap: QPixmap | None = index.data(Qt.ItemDataRole.UserRole)
        if isinstance(pixmap, QPixmap) and not pixmap.isNull():
            x = option.rect.x() + (option.rect.width() - pixmap.width()) // 2
            y = option.rect.y() + (option.rect.height() - pixmap.height()) // 2
            if option.state & QStyle.StateFlag.State_MouseOver:
                palette = template_palette()
                painter.save()
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                painter.setPen(QPen(QColor(palette["accent"]), 2))
                painter.setBrush(QColor(palette["accent_soft"]))
                painter.drawRoundedRect(QRectF(x - 6, y - 6, pixmap.width() + 12, pixmap.height() + 12), 10, 10)
                painter.restore()
            painter.drawPixmap(x, y, pixmap)


class StatusIconDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        return QSize(76, 52)

    def paint(self, painter, option, index):
        style = option.widget.style() if option.widget else QApplication.style()
        style.drawPrimitive(QStyle.PrimitiveElement.PE_PanelItemViewItem, option, painter, option.widget)
        value = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        palette = template_palette()
        color, glyph = _status_icon(value, palette)
        _draw_badge_icon(painter, option.rect, color, glyph)


class QualityIconDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        return QSize(76, 52)

    def paint(self, painter, option, index):
        style = option.widget.style() if option.widget else QApplication.style()
        style.drawPrimitive(QStyle.PrimitiveElement.PE_PanelItemViewItem, option, painter, option.widget)
        value = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        palette = template_palette()
        _draw_quality_bars(painter, option.rect, value, palette)


class RegionBadgeDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        return QSize(96, 52)

    def paint(self, painter, option, index):
        style = option.widget.style() if option.widget else QApplication.style()
        style.drawPrimitive(QStyle.PrimitiveElement.PE_PanelItemViewItem, option, painter, option.widget)
        value = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        palette = template_palette()
        _draw_region_badges(painter, option.rect, value, palette)


def _status_icon(value: str, palette: dict) -> tuple[str, str]:
    normalized = value.lower()
    if normalized in {"correcta", "guardado"}:
        return palette["success"], "v"
    if normalized in {"seleccionada", "propuesta_auto"}:
        return palette["accent"], "*"
    if normalized in {"revision", "dudosa", "pendiente_guardar"}:
        return palette["warning"], "!"
    if normalized in {"faltante", "sin_caratula", "pendiente_eliminar", "error"}:
        return palette["danger"], "x"
    if normalized in {"omitida"}:
        return palette["muted"], "-"
    return palette["muted"], "?"


def _draw_region_badges(painter: QPainter, rect, value: str, palette: dict) -> None:
    labels = [part for part in value.split() if part and part != "REG?"]
    if not labels:
        labels = ["?"]
    colors = {
        "US": "#2d6cdf",
        "JP": "#c84537",
        "EU": "#d18400",
        "?": palette["muted"],
    }
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    font = QFont("Segoe UI", 8)
    font.setBold(True)
    painter.setFont(font)
    badge_width = 26
    gap = 4
    total_width = len(labels) * badge_width + (len(labels) - 1) * gap
    x = rect.center().x() - total_width / 2
    y = rect.center().y() - 12
    for label in labels:
        badge = QRectF(x, y, badge_width, 24)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(colors.get(label, palette["muted"])))
        painter.drawRoundedRect(badge, 8, 8)
        painter.setPen(QColor("#fffdf8"))
        painter.drawText(badge, int(Qt.AlignmentFlag.AlignCenter), label)
        x += badge_width + gap
    painter.restore()


def _draw_badge_icon(painter: QPainter, rect, color: str, glyph: str) -> None:
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    center = rect.center()
    diameter = min(30, rect.width() - 12, rect.height() - 12)
    badge = QRectF(center.x() - diameter / 2, center.y() - diameter / 2, diameter, diameter)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color))
    painter.drawEllipse(badge)
    font = QFont("Segoe UI", 13)
    font.setBold(True)
    painter.setFont(font)
    painter.setPen(QColor("#fffdf8"))
    painter.drawText(badge, int(Qt.AlignmentFlag.AlignCenter), glyph)
    painter.restore()


def _draw_quality_bars(painter: QPainter, rect, value: str, palette: dict) -> None:
    normalized = value.strip().lower()
    if normalized == "alta":
        bars, color = 3, palette["success"]
    elif normalized == "aceptable":
        bars, color = 2, palette["accent"]
    elif normalized == "baja":
        bars, color = 1, palette["warning"]
    elif normalized == "rechazar":
        bars, color = 0, palette["danger"]
    else:
        bars, color = -1, palette["muted"]

    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    center = rect.center()
    if bars < 0:
        _draw_badge_icon(painter, rect, color, "?")
        painter.restore()
        return
    if bars == 0:
        _draw_badge_icon(painter, rect, color, "×")
        painter.restore()
        return

    total_width = 34
    gap = 4
    bar_width = 8
    max_height = 28
    start_x = center.x() - total_width / 2
    bottom = center.y() + max_height / 2
    painter.setPen(Qt.PenStyle.NoPen)
    for index in range(3):
        height = 10 + index * 8
        fill = QColor(color if index < bars else palette["border"])
        painter.setBrush(fill)
        x = start_x + index * (bar_width + gap)
        y = bottom - height
        painter.drawRoundedRect(QRectF(x, y, bar_width, height), 3, 3)
    painter.restore()

