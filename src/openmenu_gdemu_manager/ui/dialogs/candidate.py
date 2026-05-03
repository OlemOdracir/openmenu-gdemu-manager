from __future__ import annotations

import logging
import os
import urllib.parse
import webbrowser
from pathlib import Path

from PIL import Image
from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QCursor, QLinearGradient, QPainter, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QProgressBar,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ... import APP_NAME
from ..image_qt import file_to_pixmap, pil_to_pixmap
from ...core.dedupe import exact_image_hash
from ...core.image_quality import analyze_image
from ...core.models import Candidate, GameItem
from ...covers.search import load_candidate_image
from ...covers.providers.registry import source_provider_id
from ...config.settings import load_settings, web_search_templates
from ...i18n import tr, translate_status
from ..theme import template_palette
from ..widgets import action_button, chip_label, region_to_flag, SpinnerLabel
from ..workers import SearchWorker, start_worker

log = logging.getLogger(__name__)

_CARD_H = 265
_GRADIENT_H = 76    # dark overlay strip height at card bottom

_QUALITY_BADGE: dict[str, tuple[str, str]] = {
    "Alta":      ("dialog.candidate.quality_max",  "Success"),
    "Aceptable": ("dialog.candidate.quality_high", "Success"),
    "Baja":      ("dialog.candidate.quality_mid",  "Warning"),
    "Rechazar":  ("dialog.candidate.quality_low",  "Danger"),
}

_REGION_COUNTRY: dict[str, str] = {
    "U": "region.usa",
    "E": "region.eur",
    "P": "region.eur",
    "J": "region.jpn",
}


def _region_country(region: str) -> str:
    for key, i18n_key in _REGION_COUNTRY.items():
        if key in (region or "").upper():
            return tr(i18n_key)
    return ""




class _GradientStrip(QWidget):
    """Bottom overlay: transparent-to-dark gradient with title + region + source."""

    def __init__(self, title: str, region: str, source: str, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 12, 8, 6)
        layout.setSpacing(2)
        layout.addStretch(1)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("color: white; font-size: 9pt; font-weight: 700; background: transparent;")
        title_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        title_lbl.setToolTip(title)
        layout.addWidget(title_lbl)

        meta_row = QHBoxLayout()
        meta_row.setSpacing(4)
        meta_row.setContentsMargins(0, 0, 0, 0)

        country = _region_country(region)
        if country:
            region_lbl = QLabel(country)
            region_lbl.setStyleSheet("color: rgba(255,255,255,0.85); font-size: 8pt; background: transparent;")
            meta_row.addWidget(region_lbl)

        if source:
            source_lbl = QLabel(source)
            source_lbl.setStyleSheet("color: rgba(200,200,200,0.9); font-size: 8pt; background: transparent;")
            meta_row.addWidget(source_lbl)

        meta_row.addStretch(1)
        layout.addLayout(meta_row)

    def paintEvent(self, event):
        p = QPainter(self)
        grad = QLinearGradient(0, 0, 0, self.height())
        grad.setColorAt(0.0, QColor(0, 0, 0, 0))
        grad.setColorAt(1.0, QColor(0, 0, 0, 210))
        p.fillRect(self.rect(), grad)


class _CandidateCard(QFrame):
    """
    Card widget with full-bleed image, dark gradient strip at bottom (title+region+source),
    quality badge top-left, select button top-right.
    Click image area → on_detail(); click select button → on_select().
    """

    def __init__(
        self,
        candidate: Candidate,
        image: Image.Image | None,
        pixmap: QPixmap | None,
        on_select,
        on_detail,
        palette: dict,
        is_current: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("CandidateCard")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(_CARD_H)
        self._on_detail = on_detail
        self._pixmap = pixmap
        self._palette = palette
        self._accepted = is_current
        self._is_current = is_current

        # ── Image (z-order: bottom)
        self._img = QLabel(self)
        self._img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._img.setStyleSheet("border: none; background: transparent;")
        if pixmap is None:
            self._img.setText(tr("dialog.candidate.no_preview"))
            self._img.setObjectName("MutedLabel")

        # ── Gradient strip (z-order: middle)
        provider = source_provider_id(candidate.source) or ""
        self._grad = _GradientStrip(candidate.title, candidate.region, provider, self)

        # ── Quality badge (z-order: top)
        self._badge: QLabel | None = None
        if image is not None:
            try:
                q = analyze_image(image)
                i18n_key, variant = _QUALITY_BADGE.get(q.label, ("dialog.candidate.quality_mid", "Warning"))
                badge = QLabel(tr(i18n_key))
                badge.setObjectName(f"QualityBadge{variant}")
                badge.setParent(self)
                badge.adjustSize()
                self._badge = badge
            except Exception:
                pass

        # ── Select button (z-order: top)
        self._sel_btn = action_button(
            self, "candidate_pick", tr("dialog.candidate.select_image"),
            variant="default", label="",
        )
        self._sel_btn.setParent(self)
        self._sel_btn.clicked.connect(lambda: on_select(self))
        self._sel_btn.adjustSize()
        self._apply_button_state()

        self._reposition()

    def set_selected(self, selected: bool):
        self._is_current = selected
        self._accepted = selected
        self._apply_button_state()
        if selected:
            c = self._palette.get("success", "#1f8a4d")
            self.setStyleSheet(f"QFrame#CandidateCard {{ border: 3px solid {c}; border-radius: 14px; }}")
        else:
            self.setStyleSheet("")

    def play_accept_feedback(self):
        self._accepted = True
        self._is_current = True
        self._sel_btn.setEnabled(False)
        self._apply_button_state()
        c = self._palette.get("success", "#1f8a4d")
        self.setStyleSheet(
            "QFrame#CandidateCard {"
            f"border: 4px solid {c};"
            "border-radius: 14px;"
            "background: rgba(31, 138, 77, 0.08);"
            "}"
        )
        self.update()
        self._reposition()

    def _apply_button_state(self):
        from ..icons import action_qicon

        if self._is_current or self._accepted:
            self._sel_btn.setIcon(action_qicon("select", "success", 22))
            self._sel_btn.setProperty("variant", "success")
            self._sel_btn.setToolTip(tr("dialog.candidate.current_cover"))
            self._sel_btn.setStyleSheet("")
        else:
            self._sel_btn.setIcon(action_qicon("candidate_pick", "default", 22))
            self._sel_btn.setProperty("variant", "default")
            self._sel_btn.setToolTip(tr("dialog.candidate.select_image"))
            self._sel_btn.setStyleSheet(
                "QPushButton {"
                "background: rgba(255, 255, 255, 0.38);"
                "border: 1px solid rgba(255, 255, 255, 0.7);"
                "border-radius: 12px;"
                "}"
                "QPushButton:hover {"
                "background: rgba(255, 255, 255, 0.72);"
                "}"
            )
        self._sel_btn.style().unpolish(self._sel_btn)
        self._sel_btn.style().polish(self._sel_btn)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.width() > 0 and abs(self.height() - self.width()) > 2:
            self.setFixedHeight(self.width())
        self._reposition()

    def _reposition(self):
        w, h = self.width(), self.height()
        self._img.setGeometry(0, 0, w, h)
        if self._pixmap and w > 0 and h > 0:
            self._img.setPixmap(
                self._pixmap.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            )
        self._grad.setGeometry(0, h - _GRADIENT_H, w, _GRADIENT_H)
        self._grad.raise_()
        if self._badge:
            self._badge.adjustSize()
            self._badge.move(8, 8)
            self._badge.raise_()
        self._sel_btn.adjustSize()
        btn_w = self._sel_btn.width()
        btn_h = self._sel_btn.height()
        if self._accepted:
            btn_w += 4
            btn_h += 4
        self._sel_btn.setGeometry(w - btn_w - 6, 6, btn_w, btn_h)
        self._sel_btn.raise_()

    def mousePressEvent(self, event):
        if self._on_detail:
            self._on_detail()
        else:
            super().mousePressEvent(event)

    def enterEvent(self, event):
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.unsetCursor()
        super().leaveEvent(event)


# ── Detail dialog ─────────────────────────────────────────────────────────────

class CandidateDetailDialog(QDialog):
    use_requested = Signal(object)

    def __init__(self, candidate: Candidate, image: Image.Image, parent=None):
        super().__init__(parent)
        self.candidate = candidate
        self.image = image
        self.setWindowTitle(tr("dialog.candidate.detail_title"))
        self.resize(700, 720)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        image_frame = QFrame()
        image_frame.setObjectName("StatusCard")
        ifl = QVBoxLayout(image_frame)
        ifl.setContentsMargins(12, 12, 12, 12)
        img_lbl = QLabel()
        img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img_lbl.setMinimumSize(480, 440)
        img_lbl.setObjectName("CandidatePreview")
        try:
            img_lbl.setPixmap(pil_to_pixmap(self.image, (560, 480)))
        except Exception:
            img_lbl.setText(tr("dialog.candidate.no_preview"))
        ifl.addWidget(img_lbl)
        root.addWidget(image_frame, 1)

        use_btn = action_button(
            self, "select", tr("dialog.candidate.use_this"),
            variant="success", label=tr("dialog.candidate.use_this"),
        )
        use_btn.clicked.connect(self._on_use)
        use_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        root.addWidget(use_btn)

        details = QWidget()
        details.setObjectName("FilterBar")
        dl = QHBoxLayout(details)
        dl.setContentsMargins(14, 10, 14, 10)
        dl.setSpacing(20)

        c = self.candidate
        try:
            q = analyze_image(self.image)
            quality_text = f"{q.label} ({q.score})"
        except Exception:
            quality_text = c.quality_label or "-"

        match_mark = "ID" if c.product_match else ("AL" if c.alias_match else ("WK" if c.weak_match else "NM"))
        resolution = f"{c.width}×{c.height}" if c.width and c.height else "-"
        provider = source_provider_id(c.source) or c.source

        for label, value in [
            (tr("dialog.candidate.provider"), provider),
            (tr("table.region"), region_to_flag(c.region) if c.region else "-"),
            ("Calidad", quality_text),
            (tr("dialog.candidate.resolution"), resolution),
            (tr("dialog.candidate.match_type"), match_mark),
        ]:
            col = QVBoxLayout()
            n = QLabel(label)
            n.setObjectName("MutedLabel")
            v = QLabel(str(value))
            v.setObjectName("TileTitle")
            col.addWidget(n)
            col.addWidget(v)
            dl.addLayout(col)

        if c.duplicate_sources:
            col = QVBoxLayout()
            n = QLabel("También en")
            n.setObjectName("MutedLabel")
            v = QLabel(", ".join(c.duplicate_sources))
            v.setObjectName("TileTitle")
            v.setWordWrap(True)
            col.addWidget(n)
            col.addWidget(v)
            dl.addLayout(col)

        dl.addStretch(1)
        root.addWidget(details)

        title_lbl = QLabel(c.title)
        title_lbl.setObjectName("WizardSubtitle")
        title_lbl.setWordWrap(True)
        root.addWidget(title_lbl)

    def _on_use(self):
        self.use_requested.emit(self.candidate)
        self.accept()


# ── Main dialog ───────────────────────────────────────────────────────────────

class CandidateDialog(QDialog):
    selected = Signal(object, object)
    name_saved = Signal(str)

    def __init__(self, game: GameItem, parent=None, *, auto_search: bool = False):
        super().__init__(parent)
        self.game = game
        self.settings = load_settings()
        self.candidates: list[Candidate] = []
        self._loaded: dict[int, Image.Image] = {}
        self._page: int = 0
        self._per_page: int = 9
        self._current_cover_hashes: set[str] = set()
        self._auto_search = auto_search
        self._auto_search_started = False
        self.search_thread: QThread | None = None
        self.search_worker: SearchWorker | None = None
        self.setWindowTitle(f"{game.slot:03d} - {game.name}")
        self.resize(1100, 820)
        try:
            self._build_ui()
        except Exception as exc:
            log.exception("CandidateDialog build failed")
            QMessageBox.warning(self, APP_NAME, tr("dialog.candidate.open_failed", message=exc))

    def showEvent(self, event):
        super().showEvent(event)
        if self._auto_search and not self._auto_search_started and not self.candidates:
            self._auto_search_started = True
            QTimer.singleShot(0, lambda: self.safe_call(self.start_search))

    def _build_ui(self):
        from ...core.matching import strip_disc
        root = QHBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        # ── Left sidebar ──────────────────────────────────────────────────────
        sidebar = QFrame()
        sidebar.setObjectName("StatusCard")
        sidebar.setFixedWidth(230)
        sidebar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        sl = QVBoxLayout(sidebar)
        sl.setContentsMargins(14, 14, 14, 14)
        sl.setSpacing(10)

        self.current_cover = QLabel(tr("dialog.candidate.no_current_cover"))
        self.current_cover.setObjectName("CurrentCover")
        self.current_cover.setFixedSize(200, 200)
        self.current_cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if self.game.current_cover and Path(self.game.current_cover).exists():
            try:
                self.current_cover.setPixmap(file_to_pixmap(self.game.current_cover, (192, 192)))
            except Exception as exc:
                log.exception("Could not load current cover: %s", self.game.current_cover)
                self.current_cover.setText(tr("dialog.candidate.image_error", message=exc))
        sl.addWidget(self.current_cover, 0, Qt.AlignmentFlag.AlignHCenter)

        meta = QGridLayout()
        meta.setContentsMargins(0, 4, 0, 0)
        meta.setSpacing(4)
        meta.setColumnStretch(1, 1)

        def _meta_row(row: int, label: str, value: str):
            lbl = QLabel(label)
            lbl.setObjectName("MutedLabel")
            lbl.setStyleSheet("font-size: 9pt;")
            val = QLabel(value)
            val.setObjectName("TileTitle")
            val.setStyleSheet("font-size: 9pt; font-weight: 700;")
            val.setWordWrap(True)
            meta.addWidget(lbl, row, 0)
            meta.addWidget(val, row, 1)

        _meta_row(0, tr("table.slot"), f"{self.game.slot:03d}")
        _meta_row(1, tr("table.product_id"), self.game.product_id or "-")
        _r = self.game.region or ""
        _country = _region_country(_r)
        _region_display = f"{region_to_flag(_r)}  {_country}" if _country else (region_to_flag(_r) or _r or "-")
        _meta_row(2, tr("dialog.candidate.game_region"), _region_display)
        self._name_meta_val: QLabel = QLabel()  # updated on name save
        self._name_meta_val.setObjectName("TileTitle")
        self._name_meta_val.setStyleSheet("font-size: 9pt; font-weight: 700;")
        self._name_meta_val.setWordWrap(True)
        name_lbl = QLabel(tr("table.name"))
        name_lbl.setObjectName("MutedLabel")
        name_lbl.setStyleSheet("font-size: 9pt;")
        meta.addWidget(name_lbl, 3, 0)
        meta.addWidget(self._name_meta_val, 3, 1)
        _meta_row(4, tr("table.status"), translate_status(self.game.status))
        current_quality = self._current_cover_quality_text()
        if current_quality:
            _meta_row(5, tr("dialog.candidate.resolution"), current_quality[0])
            _meta_row(6, tr("table.quality"), current_quality[1])

        sl.addLayout(meta)
        sl.addStretch(1)
        root.addWidget(sidebar)

        # ── Right area ────────────────────────────────────────────────────────
        right = QVBoxLayout()
        right.setSpacing(8)

        # Top bar
        top_bar = QWidget()
        top_bar.setObjectName("DialogToolbar")
        tbl = QVBoxLayout(top_bar)
        tbl.setContentsMargins(12, 10, 12, 10)
        tbl.setSpacing(6)

        title_lbl = QLabel(tr("dialog.candidate.heading"))
        title_lbl.setObjectName("SectionTitle")
        tbl.addWidget(title_lbl)

        search_row = QHBoxLayout()
        search_row.setSpacing(6)
        self.query = QLineEdit(strip_disc(self.game.name))
        search_row.addWidget(self.query, 1)

        self.search_button = action_button(self, "search", tr("dialog.candidate.search_tip"), variant="accent", label=tr("dialog.candidate.search"))
        self.search_button.clicked.connect(lambda: self.safe_call(self.start_search))
        search_row.addWidget(self.search_button)

        self.save_name_button = action_button(self, "save", tr("dialog.candidate.save_name_tip"), variant="success", label=tr("dialog.candidate.save_name"))
        self.save_name_button.clicked.connect(lambda: self.safe_call(self.save_name))
        search_row.addWidget(self.save_name_button)

        self.local_button = action_button(self, "local_file", tr("dialog.candidate.local_tip"), label=tr("dialog.candidate.file"))
        self.local_button.clicked.connect(lambda: self.safe_call(self.pick_local))
        search_row.addWidget(self.local_button)

        self.web_button = action_button(self, "web", tr("dialog.candidate.web_tip"), label="Web")
        self.web_button.clicked.connect(lambda: self.safe_call(self.open_web_search))
        search_row.addWidget(self.web_button)

        tbl.addLayout(search_row)
        right.addWidget(top_bar)

        # Loading row
        loading_row = QHBoxLayout()
        self.search_spinner = SpinnerLabel(self)
        loading_row.addWidget(self.search_spinner, 0, Qt.AlignmentFlag.AlignVCenter)
        self.loading = QProgressBar()
        self.loading.setRange(0, 0)
        self.loading.setVisible(False)
        loading_row.addWidget(self.loading, 1)
        right.addLayout(loading_row)

        self.status = QLabel(tr("dialog.candidate.initial_status"))
        self.status.setObjectName("MutedLabel")
        self.status.setWordWrap(True)
        right.addWidget(self.status)

        # Grid scroll area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.cards_container = QWidget()
        self.cards_layout = QGridLayout(self.cards_container)
        self.cards_layout.setSpacing(8)
        self.cards_layout.setContentsMargins(4, 4, 4, 4)
        for col in range(3):
            self.cards_layout.setColumnStretch(col, 1)
        self.cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.cards_container)
        right.addWidget(self.scroll, 1)

        # Footer
        footer = QWidget()
        footer.setObjectName("DialogToolbar")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(12, 6, 12, 6)
        fl.setSpacing(8)

        self.results_label = QLabel("")
        self.results_label.setObjectName("MutedLabel")
        fl.addWidget(self.results_label)
        fl.addStretch(1)

        self.page_label = QLabel("")
        self.page_label.setObjectName("MutedLabel")
        fl.addWidget(self.page_label)

        self.prev_button = action_button(self, "back", "Anterior", label="←")
        self.prev_button.clicked.connect(self._prev_page)
        fl.addWidget(self.prev_button)

        self.next_button = action_button(self, "forward", "Siguiente", label="→")
        self.next_button.clicked.connect(self._next_page)
        fl.addWidget(self.next_button)

        refresh_btn = action_button(self, "search", tr("dialog.candidate.refresh_search"), variant="accent", label=tr("dialog.candidate.refresh_search"))
        refresh_btn.clicked.connect(lambda: self.safe_call(self.start_search))
        fl.addWidget(refresh_btn)

        right.addWidget(footer)
        root.addLayout(right, 1)

        self._refresh_game_header()
        self._update_footer()

    # ── Header ────────────────────────────────────────────────────────────────

    def _refresh_game_header(self):
        self.setWindowTitle(f"{self.game.slot:03d} - {self.game.name}")
        self._name_meta_val.setText(self.game.name)

    def _current_cover_quality_text(self) -> tuple[str, str] | None:
        cover_path = Path(self.game.current_cover) if self.game.current_cover else None
        if cover_path is None or not cover_path.exists():
            return None
        try:
            with Image.open(cover_path) as image:
                quality = analyze_image(image)
        except Exception:
            log.exception("Could not analyze current cover: %s", cover_path)
            return None
        return f"{quality.width}x{quality.height}", f"{quality.label} ({quality.score})"

    def _set_search_busy(self, busy: bool, message: str = ""):
        for btn in (self.search_button, self.save_name_button, self.local_button, self.web_button):
            btn.setEnabled(not busy)
        self.loading.setVisible(busy)
        if busy:
            self.search_spinner.start()
            self.status.setText(message or tr("dialog.candidate.searching"))
        else:
            self.search_spinner.stop()

    # ── Search ────────────────────────────────────────────────────────────────

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

    def show_candidates(self, result):
        try:
            new_count = 0
            saved_count = 0
            if isinstance(result, dict):
                candidates = list(result.get("candidates") or [])
                new_count = int(result.get("new_count") or 0)
                saved_count = int(result.get("saved_count") or 0)
            else:
                candidates = list(result or [])
            self._set_search_busy(False)
            self.candidates = candidates
            self._page = 0
            self._loaded.clear()
            if new_count > 0:
                self.status.setText(tr("dialog.candidate.new_results", count=new_count, total=len(candidates)))
            elif saved_count > 0:
                self.status.setText(tr("dialog.candidate.no_new_results", count=len(candidates)))
            elif len(candidates) < 6:
                self.status.setText(tr("dialog.candidate.few_results", count=len(candidates)))
            else:
                self.status.setText(tr("dialog.candidate.results", count=len(candidates)))
            self._render_page()
        except Exception as exc:
            self._set_search_busy(False)
            self.show_error(tr("dialog.candidate.show_failed", message=exc))

    def show_error(self, message: str):
        log.error("Candidate dialog error: %s", message)
        self._set_search_busy(False)
        self.status.setText(tr("app.error", message=message))

    # ── Grid / pagination ─────────────────────────────────────────────────────

    def _clear_cards(self):
        self._loaded.clear()
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _render_page(self):
        self._clear_cards()
        palette = template_palette()
        start = self._page * self._per_page
        for idx, candidate in enumerate(self.candidates[start: start + self._per_page]):
            global_idx = start + idx
            image: Image.Image | None = None
            pixmap: QPixmap | None = None
            try:
                image = load_candidate_image(candidate)
                pixmap = pil_to_pixmap(image, (600, _CARD_H * 2))
                self._loaded[global_idx] = image
            except Exception as exc:
                log.debug("Preview failed for %s: %s", candidate.title, exc)

            row, col = divmod(idx, 3)
            on_select = (lambda card, c=candidate: self.safe_call(lambda: self._accept_card_candidate(c, card)))
            on_detail = (lambda c=candidate, g=global_idx: self.safe_call(lambda: self._open_detail(c, g)))
            card = _CandidateCard(
                candidate,
                image,
                pixmap,
                on_select,
                on_detail,
                palette,
                is_current=self._candidate_is_current_cover(candidate, image),
                parent=self.cards_container,
            )
            self.cards_layout.addWidget(card, row, col)

        self._update_footer()

    def _update_footer(self):
        total = len(self.candidates)
        pages = max(1, -(-total // self._per_page))
        self.results_label.setText(tr("dialog.candidate.results_count", count=total))
        if pages > 1:
            self.page_label.setText(tr("dialog.candidate.page_of", page=self._page + 1, total=pages))
            self.page_label.setVisible(True)
            self.prev_button.setVisible(True)
            self.next_button.setVisible(True)
            self.prev_button.setEnabled(self._page > 0)
            self.next_button.setEnabled(self._page < pages - 1)
        else:
            self.page_label.setVisible(False)
            self.prev_button.setVisible(False)
            self.next_button.setVisible(False)

    def _prev_page(self):
        if self._page > 0:
            self._page -= 1
            self._render_page()
            self.scroll.verticalScrollBar().setValue(0)

    def _next_page(self):
        pages = max(1, -(-len(self.candidates) // self._per_page))
        if self._page < pages - 1:
            self._page += 1
            self._render_page()
            self.scroll.verticalScrollBar().setValue(0)

    # ── Card actions ──────────────────────────────────────────────────────────

    def _accept_card_candidate(self, candidate: Candidate, card: _CandidateCard):
        card.play_accept_feedback()
        self.status.setText(tr("dialog.candidate.selection_confirmed"))
        self._set_controls_enabled(False)
        QTimer.singleShot(180, lambda: self._select_after_feedback(candidate))

    def _set_controls_enabled(self, enabled: bool):
        for btn in (self.search_button, self.save_name_button, self.local_button, self.web_button, self.prev_button, self.next_button):
            btn.setEnabled(enabled)

    def _select_after_feedback(self, candidate: Candidate):
        before_closed = self.isVisible()
        self.select_candidate(candidate)
        if before_closed and self.isVisible():
            self._set_controls_enabled(True)
            self._update_footer()

    def _open_detail(self, candidate: Candidate, global_idx: int):
        image = self._loaded.get(global_idx)
        if image is None:
            try:
                image = load_candidate_image(candidate)
            except Exception as exc:
                QMessageBox.warning(self, APP_NAME, tr("dialog.candidate.load_image_failed", message=exc))
                return
        dlg = CandidateDetailDialog(candidate, image, parent=self)
        dlg.use_requested.connect(lambda c: self.safe_call(lambda: self.select_candidate(c)))
        dlg.exec()

    def _candidate_is_current_cover(self, candidate: Candidate, image: Image.Image | None) -> bool:
        hashes = self._current_hashes()
        if not hashes:
            return False
        if candidate.exact_hash and candidate.exact_hash in hashes:
            return True
        if image is None:
            return False
        try:
            return exact_image_hash(image) in hashes
        except Exception:
            return False

    def _current_hashes(self) -> set[str]:
        if self._current_cover_hashes:
            return self._current_cover_hashes
        for raw in (self.game.original_image, self.game.selected_image, str(self.game.current_cover or "")):
            if not raw:
                continue
            path = Path(raw)
            if not path.exists():
                continue
            try:
                with Image.open(path) as image:
                    self._current_cover_hashes.add(exact_image_hash(image))
            except Exception:
                log.debug("Could not hash current cover candidate: %s", path)
        return self._current_cover_hashes

    def select_candidate(self, candidate: Candidate):
        try:
            image = load_candidate_image(candidate)
        except Exception as exc:
            QMessageBox.warning(self, APP_NAME, tr("dialog.candidate.load_image_failed", message=exc))
            return
        self.selected.emit(candidate, image)
        self.accept()

    # ── Other actions ─────────────────────────────────────────────────────────

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
