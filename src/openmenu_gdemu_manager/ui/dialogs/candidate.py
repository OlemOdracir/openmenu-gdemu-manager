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
from ..image_qt import file_to_pixmap, pil_to_pixmap
from ...core.image_quality import analyze_image
from ...core.models import Candidate, GameItem, RomLibraryEntry
from ...core.placeholder import ensure_no_cover_asset
from ...dreamcast.rom_library import inspect_source, scan_rom_library
from ...covers.search import load_candidate_image
from ...config.settings import load_settings, web_search_templates
from ...dreamcast.storage_diagnostics import StorageDiagnostic, diagnose_storage
from ...i18n import tr, translate_status
from ..theme import template_palette
from ..widgets import action_button, chip_label, region_to_flag, SpinnerLabel
from ..workers import SearchWorker, start_worker

log = logging.getLogger(__name__)


class CandidateDialog(QDialog):
    selected = Signal(object, object)
    name_saved = Signal(str)

    def __init__(self, game: GameItem, parent=None):
        super().__init__(parent)
        self.game = game
        self.settings = load_settings()
        self.candidates: list[Candidate] = []
        self.card_images: list = []
        self.search_thread: QThread | None = None
        self.search_worker: SearchWorker | None = None
        self.setWindowTitle(f"{game.slot:03d} - {game.name}")
        self.resize(980, 720)
        try:
            self._build_ui()
        except Exception as exc:
            log.exception("CandidateDialog build failed")
            QMessageBox.warning(self, APP_NAME, tr("dialog.candidate.open_failed", message=exc))

    def _build_ui(self):
        from ...core.matching import strip_disc
        layout = QVBoxLayout(self)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.addWidget(chip_label(f"{tr('table.slot')} {self.game.slot:03d}", "accent"))
        header_layout.addWidget(chip_label(f"Product ID {self.game.product_id or '-'}"))
        header_layout.addWidget(chip_label(f"{tr('table.region')} {region_to_flag(self.game.region)} {self.game.region or '-'}"))
        header_layout.addWidget(chip_label(f"{tr('table.status')} {translate_status(self.game.status)}", "success" if self.game.status in {"correcta", "seleccionada"} else "warning"))
        self.saved_name_chip = chip_label(tr("dialog.candidate.saved_name", name=self.game.name))
        header_layout.addWidget(self.saved_name_chip, 1)
        layout.addWidget(header)

        top = QHBoxLayout()
        self.current_cover = QLabel(tr("dialog.candidate.no_current_cover"))
        self.current_cover.setObjectName("CurrentCover")
        self.current_cover.setFixedSize(220, 220)
        self.current_cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if self.game.current_cover and Path(self.game.current_cover).exists():
            try:
                self.current_cover.setPixmap(file_to_pixmap(self.game.current_cover, (210, 210)))
            except Exception as exc:
                log.exception("Could not load current cover in dialog: %s", self.game.current_cover)
                self.current_cover.setText(tr("dialog.candidate.image_error", message=exc))
        top.addWidget(self.current_cover)

        search_box = QVBoxLayout()
        self.query = QLineEdit(strip_disc(self.game.name))
        title = QLabel(tr("dialog.candidate.heading"))
        title.setObjectName("SectionTitle")
        search_box.addWidget(title)
        search_box.addWidget(self.query)

        toolbar = QWidget()
        toolbar.setObjectName("DialogToolbar")
        buttons = QHBoxLayout(toolbar)
        buttons.setContentsMargins(10, 10, 10, 10)
        self.search_button = action_button(self, "search", tr("dialog.candidate.search_tip"), variant="accent", label=tr("dialog.candidate.search"))
        self.search_button.clicked.connect(lambda: self.safe_call(self.start_search))
        buttons.addWidget(self.search_button)
        self.save_name_button = action_button(self, "save", tr("dialog.candidate.save_name_tip"), variant="success", label=tr("dialog.candidate.save_name"))
        self.save_name_button.clicked.connect(lambda: self.safe_call(self.save_name))
        buttons.addWidget(self.save_name_button)
        self.local_button = action_button(self, "local_file", tr("dialog.candidate.local_tip"), label=tr("dialog.candidate.file"))
        self.local_button.clicked.connect(lambda: self.safe_call(self.pick_local))
        buttons.addWidget(self.local_button)
        self.web_button = action_button(self, "web", tr("dialog.candidate.web_tip"), label="Web")
        self.web_button.clicked.connect(lambda: self.safe_call(self.open_web_search))
        buttons.addWidget(self.web_button)
        search_box.addWidget(toolbar)

        loading_row = QHBoxLayout()
        self.search_spinner = SpinnerLabel(self)
        loading_row.addWidget(self.search_spinner, 0, Qt.AlignmentFlag.AlignVCenter)
        self.loading = QProgressBar()
        self.loading.setRange(0, 0)
        self.loading.setVisible(False)
        loading_row.addWidget(self.loading, 1)
        search_box.addLayout(loading_row)

        self.status = QLabel(tr("dialog.candidate.initial_status"))
        self.status.setObjectName("MutedLabel")
        self.status.setWordWrap(True)
        search_box.addWidget(self.status)
        top.addLayout(search_box)
        layout.addLayout(top)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.cards_container = QWidget()
        self.cards_layout = QGridLayout(self.cards_container)
        self.scroll.setWidget(self.cards_container)
        layout.addWidget(self.scroll, 1)

        close = action_button(self, "close", tr("action.close"), width=44, label=tr("action.close"))
        close.clicked.connect(self.accept)
        layout.addWidget(close)
        self._refresh_game_header()

    def _refresh_game_header(self):
        self.setWindowTitle(f"{self.game.slot:03d} - {self.game.name}")
        self.saved_name_chip.setText(tr("dialog.candidate.saved_name", name=self.game.name))

    def _set_search_busy(self, busy: bool, message: str = ""):
        self.search_button.setEnabled(not busy)
        self.save_name_button.setEnabled(not busy)
        self.local_button.setEnabled(not busy)
        self.web_button.setEnabled(not busy)
        self.loading.setVisible(busy)
        if busy:
            self.search_spinner.start()
            self.status.setText(message or tr("dialog.candidate.searching"))
        else:
            self.search_spinner.stop()

    def start_search(self):
        query = self.query.text().strip()
        if not query:
            return
        if self.search_thread is not None and self.search_thread.isRunning():
            QMessageBox.information(self, APP_NAME, tr("dialog.candidate.search_running"))
            return
        self._set_search_busy(True, tr("dialog.candidate.searching"))
        self._clear_cards()
        _sw = SearchWorker(self.game, query)
        start_worker(_sw, "search_thread", "search_worker", self,
                     on_finished=self.show_candidates, on_error=self.show_error)

    def show_candidates(self, candidates: list[Candidate]):
        try:
            self._set_search_busy(False)
            self.candidates = candidates
            self.status.setText(tr("dialog.candidate.loading_previews", count=len(candidates)))
            self._clear_cards()
            visible_limit = int(self.settings.get("visible_candidate_limit", 18) or 18)
            for idx, candidate in enumerate(candidates[:visible_limit]):
                self._add_card(idx, candidate)
            if len(candidates) < 6:
                self.status.setText(
                    tr("dialog.candidate.few_results", count=len(candidates))
                )
            else:
                self.status.setText(tr("dialog.candidate.results", count=len(candidates)))
        except Exception as exc:
            self._set_search_busy(False)
            self.show_error(tr("dialog.candidate.show_failed", message=exc))

    def show_error(self, message: str):
        log.error("Candidate dialog error: %s", message)
        self._set_search_busy(False)
        self.status.setText(tr("app.error", message=message))

    def _clear_cards(self):
        self.card_images.clear()
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _add_card(self, idx: int, candidate: Candidate):
        box = QGroupBox(candidate.display)
        box_layout = QVBoxLayout(box)
        preview = QLabel(tr("dialog.candidate.no_preview"))
        preview.setObjectName("CandidatePreview")
        preview.setFixedSize(190, 190)
        preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        try:
            image = load_candidate_image(candidate)
            quality = analyze_image(image)
            box.setTitle(f"{candidate.display} | {quality.label} {quality.score}")
            duplicates = ", ".join(candidate.duplicate_sources or [])
            if duplicates:
                box.setToolTip(tr("dialog.candidate.also_found", sources=duplicates))
            pixmap = pil_to_pixmap(image, (185, 185))
            self.card_images.append(pixmap)
            preview.setPixmap(pixmap)
            qlabel = QLabel(quality.display)
            qlabel.setWordWrap(True)
            palette = template_palette()
            if not quality.accepted:
                qlabel.setStyleSheet(f"color:{palette['danger']};font-weight:bold;")
            elif quality.label == "Baja":
                qlabel.setStyleSheet(f"color:{palette['warning']};font-weight:bold;")
            else:
                qlabel.setStyleSheet(f"color:{palette['success']};font-weight:bold;")
        except Exception as exc:
            preview.setText(tr("dialog.candidate.preview_failed", message=exc))
            qlabel = QLabel(tr("dialog.candidate.quality_unavailable"))

        box_layout.addWidget(preview)
        box_layout.addWidget(qlabel)
        title = QLabel(candidate.title)
        title.setWordWrap(True)
        box_layout.addWidget(title)
        if candidate.duplicate_sources:
            duplicate_label = QLabel(tr("dialog.candidate.also_in", sources=", ".join(candidate.duplicate_sources)))
            duplicate_label.setWordWrap(True)
            duplicate_label.setObjectName("MutedLabel")
            box_layout.addWidget(duplicate_label)

        actions = QHBoxLayout()
        select = action_button(self, "select", tr("dialog.candidate.select_image"), variant="success", label=tr("dialog.candidate.use"))
        select.clicked.connect(lambda _=False, c=candidate: self.safe_call(lambda: self.select_candidate(c)))
        actions.addWidget(select)
        source = action_button(self, "source", tr("dialog.candidate.open_source"), label=tr("dialog.candidate.source"))
        source.clicked.connect(lambda _=False, c=candidate: self.safe_call(lambda: self.open_source(c)))
        actions.addWidget(source)
        box_layout.addLayout(actions)

        row = idx // 3
        col = idx % 3
        self.cards_layout.addWidget(box, row, col)

    def select_candidate(self, candidate: Candidate):
        try:
            image = load_candidate_image(candidate)
        except Exception as exc:
            QMessageBox.warning(self, APP_NAME, tr("dialog.candidate.load_image_failed", message=exc))
            return
        self.selected.emit(candidate, image)
        self.accept()

    def save_name(self):
        new_name = self.query.text().strip()
        if not new_name:
            QMessageBox.information(self, APP_NAME, tr("dialog.candidate.name_required"))
            return
        self.game.name = new_name
        self._refresh_game_header()
        self.name_saved.emit(new_name)
        self.status.setText(tr("dialog.candidate.name_saved_status"))

    def pick_local(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("dialog.candidate.choose_cover"), "", "Images (*.png *.jpg *.jpeg)")
        if not path:
            return
        try:
            image = Image.open(path).convert("RGB")
        except Exception as exc:
            QMessageBox.warning(self, APP_NAME, tr("dialog.candidate.open_image_failed", message=exc))
            return
        candidate = Candidate("archivo local", Path(path).stem, 100, local_path=path)
        self.selected.emit(candidate, image)
        self.accept()

    def open_source(self, candidate: Candidate):
        if candidate.source_url:
            webbrowser.open(candidate.source_url)
        elif candidate.url:
            webbrowser.open(candidate.url)
        elif candidate.local_path:
            os.startfile(str(Path(candidate.local_path).parent))

    def open_web_search(self):
        query = self.query.text().strip()
        if not query:
            return
        templates = web_search_templates(self.settings)
        if not templates:
            webbrowser.open("https://www.google.com/search?tbm=isch&q=" + urllib.parse.quote(f"{query} Dreamcast cover art"))
            return
        menu = QMenu(self)
        for template in templates:
            action = QAction(template["name"], self)
            action.triggered.connect(lambda _=False, t=template: self._open_web_template(t, query))
            menu.addAction(action)
        menu.exec(self.web_button.mapToGlobal(self.web_button.rect().bottomLeft()))

    def _open_web_template(self, template: dict[str, str], query: str):
        product_id = self.game.product_id or query
        url = template["url"].format(
            query=urllib.parse.quote(f"{query} Dreamcast cover art"),
            raw_query=urllib.parse.quote(query),
            product_id=urllib.parse.quote(product_id),
        )
        webbrowser.open(url)

    def safe_call(self, callback):
        try:
            callback()
        except Exception as exc:
            log.exception("Dialog callback failed")
            QMessageBox.warning(self, APP_NAME, tr("error.generic", message=exc))
            self.status.setText(tr("app.error", message=exc))

