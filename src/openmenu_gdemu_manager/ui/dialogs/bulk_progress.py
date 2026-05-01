from __future__ import annotations

import logging
import os
import urllib.parse
import webbrowser
from pathlib import Path

from PIL import Image
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ... import APP_NAME
from ...i18n import tr
from ..image_qt import file_to_pixmap, pil_to_pixmap
from ...core.image_quality import analyze_image
from ...core.models import Candidate, GameItem, RomLibraryEntry
from ...core.placeholder import ensure_no_cover_asset
from ...dreamcast.rom_library import inspect_source, scan_rom_library
from ...covers.search import load_candidate_image
from ...config.settings import load_settings, web_search_templates
from ...dreamcast.storage_diagnostics import StorageDiagnostic, diagnose_storage
from ..theme import template_palette
from ..widgets import action_button, chip_label, region_to_flag, SpinnerLabel
from ..workers import SearchWorker, start_worker

log = logging.getLogger(__name__)


class BulkProgressDialog(QDialog):
    cancel_requested = Signal()

    def __init__(self, total: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("dialog.bulk.title"))
        self.setModal(True)
        self.setFixedWidth(460)
        layout = QVBoxLayout(self)
        self.spinner = SpinnerLabel(self)
        layout.addWidget(self.spinner, 0, Qt.AlignmentFlag.AlignHCenter)
        self.spinner.start()
        self.title = QLabel(tr("dialog.bulk.processing", current=0, total=total))
        self.title.setObjectName("BusyTitle")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title)
        self.progress = QProgressBar()
        self.progress.setRange(0, total)
        self.progress.setValue(0)
        layout.addWidget(self.progress)
        self.detail = QLabel(tr("dialog.bulk.preparing"))
        self.detail.setObjectName("BusyDetail")
        self.detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail.setWordWrap(True)
        layout.addWidget(self.detail)
        self.cancel_button = action_button(self, "discard", tr("action.cancel"), variant="danger", label=tr("action.cancel"))
        self.cancel_button.clicked.connect(self._cancel)
        layout.addWidget(self.cancel_button)

    def update_progress(self, current: int, total: int, game_name: str, status_text: str):
        self.progress.setMaximum(total)
        self.progress.setValue(current)
        self.title.setText(status_text or tr("dialog.bulk.processing", current=current, total=total))
        self.detail.setText(game_name)

    def _cancel(self):
        self.cancel_button.setEnabled(False)
        self.detail.setText(tr("dialog.bulk.cancel"))
        self.cancel_requested.emit()

    def reject(self):
        self._cancel()

