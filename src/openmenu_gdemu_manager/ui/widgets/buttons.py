from __future__ import annotations

import logging
import traceback
from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSize, Qt, QTimer, Signal
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
from ...config.settings import load_settings, ui_settings
from ..icons import action_qicon
from ..theme import template_palette

log = logging.getLogger(__name__)

CONTROL_HEIGHT = 42


def apply_interactive_cursor(widget: QWidget) -> QWidget:
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    return widget


def action_button(
    owner: QWidget,
    action_name: str,
    tooltip: str,
    *,
    width: int = 40,
    variant: str = "default",
    checkable: bool = False,
    checked: bool = False,
    label: str = "",
) -> QPushButton:
    button = QPushButton("")
    ui = ui_settings(getattr(owner.window(), "settings", None) or load_settings())
    show_label = bool(ui.get("show_button_labels", False))
    text = label if show_label and label else ""
    button.setText(text)
    icon_variant = variant
    if action_name in {"search", "save", "discard", "bulk_search"} and variant == "default":
        icon_variant = "accent"
    button.setIcon(action_qicon(action_name, icon_variant, 22))
    button.setIconSize(QSize(20, 20))
    button.setToolTip(tooltip)
    button.setAccessibleName(tooltip)
    button.setProperty("variant", variant)
    button.setProperty("iconOnly", not (show_label and label))
    button.setCheckable(checkable)
    button.setChecked(checked)
    button.setFixedHeight(CONTROL_HEIGHT)
    if text:
        button.setMinimumWidth(max(width, CONTROL_HEIGHT))
    else:
        button.setFixedWidth(max(width, CONTROL_HEIGHT))
    apply_interactive_cursor(button)
    button.style().unpolish(button)
    button.style().polish(button)
    return button

