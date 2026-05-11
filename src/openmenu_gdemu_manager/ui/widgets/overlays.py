from __future__ import annotations

import logging
import traceback
from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPointF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QConicalGradient, QLinearGradient, QPainter, QPen, QPixmap
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
from ...i18n import tr
from ..theme import template_palette

log = logging.getLogger(__name__)

class SpinnerLabel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SpinnerLabel")
        self.angle = 0
        self.timer = QTimer(self)
        self.timer.setInterval(32)
        self.timer.timeout.connect(self._advance)
        self.setFixedSize(46, 46)
        self.hide()

    def _advance(self):
        self.angle = (self.angle + 9) % 360
        self.update()

    def paintEvent(self, _event):
        palette = template_palette()
        side = min(self.width(), self.height()) - 4
        rect_x = (self.width() - side) / 2
        rect_y = (self.height() - side) / 2

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.translate(self.width() / 2, self.height() / 2)
        painter.rotate(self.angle)
        painter.translate(-self.width() / 2, -self.height() / 2)

        disc_rect = self.rect().adjusted(int(rect_x), int(rect_y), -int(rect_x), -int(rect_y))
        center = QPointF(disc_rect.center())

        disc = QConicalGradient(center, -35)
        disc.setColorAt(0.00, QColor("#f8fafc"))
        disc.setColorAt(0.18, QColor(palette["accent_soft"]))
        disc.setColorAt(0.34, QColor("#ffffff"))
        disc.setColorAt(0.55, QColor(palette["surface_alt"]))
        disc.setColorAt(0.76, QColor(palette["accent"]))
        disc.setColorAt(1.00, QColor("#f8fafc"))
        painter.setPen(QPen(QColor(palette["border"]), 1))
        painter.setBrush(disc)
        painter.drawEllipse(disc_rect)

        shine = QLinearGradient(disc_rect.topLeft(), disc_rect.bottomRight())
        shine.setColorAt(0.0, QColor(255, 255, 255, 210))
        shine.setColorAt(0.45, QColor(255, 255, 255, 35))
        shine.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(shine)
        painter.drawPie(disc_rect.adjusted(5, 5, -5, -5), 30 * 16, 62 * 16)

        painter.setPen(QPen(QColor(palette["accent"]), 2))
        painter.setBrush(QColor(palette["surface"]))
        hub = disc_rect.adjusted(side // 3, side // 3, -(side // 3), -(side // 3))
        painter.drawEllipse(hub)

        painter.setPen(QPen(QColor(palette["muted"]), 1))
        painter.setBrush(QColor("#ffffff"))
        hole = disc_rect.adjusted(int(side * 0.43), int(side * 0.43), -int(side * 0.43), -int(side * 0.43))
        painter.drawEllipse(hole)

    def start(self):
        self.angle = 0
        self.show()
        self.timer.start()
        self.update()

    def stop(self):
        self.timer.stop()
        self.hide()


class BusyOverlay(QWidget):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("BusyOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.hide()

        self.panel = QWidget(self)
        self.panel.setObjectName("BusyPanel")
        self.panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QVBoxLayout(self.panel)
        layout.setContentsMargins(22, 18, 22, 18)
        self.spinner = SpinnerLabel(self.panel)
        layout.addWidget(self.spinner, 0, Qt.AlignmentFlag.AlignHCenter)
        self.title = QLabel(tr("busy.processing"))
        self.title.setObjectName("BusyTitle")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title)
        self.detail = QLabel("")
        self.detail.setObjectName("BusyDetail")
        self.detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail.setWordWrap(True)
        layout.addWidget(self.detail)

    def resizeEvent(self, _event):
        if self.parentWidget() is None:
            return
        self.setGeometry(self.parentWidget().rect())
        width = min(430, max(320, self.width() - 60))
        self.panel.resize(width, 156)
        self.panel.move((self.width() - self.panel.width()) // 2, max(24, (self.height() - self.panel.height()) // 2))

    def show_message(self, title: str, detail: str = ""):
        self.title.setText(title)
        self.detail.setText(detail)
        self.raise_()
        self.show()
        self.spinner.start()
        self.resizeEvent(None)

    def clear(self):
        self.spinner.stop()
        self.hide()

