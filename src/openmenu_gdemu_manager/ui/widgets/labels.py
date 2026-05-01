from __future__ import annotations

import logging
import traceback
from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QPushButton,
    QStyle,
    QStyledItemDelegate,
    QVBoxLayout,
    QWidget,
)

from ..image_qt import file_to_pixmap, pil_to_pixmap
from ...core.models import BulkProposal, GameItem
from ...i18n import tr
from ..theme import template_palette

log = logging.getLogger(__name__)

def error_details(exc: BaseException) -> str:
    return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))


def region_to_flag(region: str) -> str:
    region = (region or "").upper()
    labels = []
    if "J" in region:
        labels.append("JP")
    if "U" in region:
        labels.append("US")
    if "E" in region or "P" in region:
        labels.append("EU")
    return " ".join(labels) if labels else "REG?"


def quality_text(game: GameItem) -> str:
    if not game.quality_label:
        return "?"
    return game.quality_label


def quality_tooltip(game: GameItem) -> str:
    if not game.quality_label:
        return tr("status.unknown")
    return tr(
        "quality.tooltip_current",
        label=game.quality_label,
        score=game.quality_score,
        width=game.image_width,
        height=game.image_height,
        mode=game.normalization_mode or "-",
    )


def chip_label(text: str, kind: str = "neutral") -> QLabel:
    label = QLabel(text)
    label.setObjectName(
        {
            "neutral": "Chip",
            "accent": "ChipAccent",
            "success": "ChipSuccess",
            "warning": "ChipWarning",
        }.get(kind, "Chip")
    )
    return label

