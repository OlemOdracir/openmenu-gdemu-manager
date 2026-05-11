from __future__ import annotations

import logging
import os
import urllib.parse
import webbrowser
from html import escape
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QObject, QSize, Qt, QThread, Signal
from PySide6.QtGui import QAction, QIcon
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
    QStackedLayout,
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
from ...config.settings import load_settings, save_settings, web_search_templates
from ...dreamcast.storage_diagnostics import StorageDiagnostic, diagnose_storage
from ...i18n import tr
from ...services.backup_service import (
    BackupError, backup_sd_contents, backup_decision, set_backup_decision, suggested_backup_dir,
)
from ...services.sd_registry import registered_backup_exists, write_backup_registry
from ...services.setup_service import OpenMenuSetupError, install_openmenu_base
from ..theme import template_palette
from ..icons import app_logo_pixmap, sd_card_qicon, vendor_qicon
from ..widgets import chip_label, region_to_flag, SpinnerLabel
from ..workers import SearchWorker, start_worker

log = logging.getLogger(__name__)


class BackupWorker(QObject):
    progress = Signal(int, int, str)
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, source: Path, destination: Path):
        super().__init__()
        self.source = Path(source)
        self.destination = Path(destination)

    def run(self):
        try:
            result = backup_sd_contents(
                self.source,
                self.destination,
                progress=lambda current, total, name: self.progress.emit(current, total, name),
            )
            self.finished.emit(str(result))
        except (BackupError, OSError) as exc:
            self.error.emit(str(exc))
        except Exception as exc:
            log.exception("Backup failed")
            self.error.emit(str(exc))


class SetupWizardDialog(QDialog):
    def __init__(self, diagnostic: StorageDiagnostic | None = None, parent=None, force_backup_prompt: bool = False):
        super().__init__(parent)
        self.diagnostic = diagnostic
        self.settings = load_settings()
        self.force_backup_prompt = force_backup_prompt
        self.selected_path: Path | None = diagnostic.root if diagnostic else None
        self.backup_thread: QThread | None = None
        self.backup_worker: BackupWorker | None = None
        self.tile_widgets: dict[str, QWidget] = {}
        self.tile_icons: dict[str, QLabel] = {}
        self.tile_count_badges: dict[str, QLabel] = {}
        self.tile_values: dict[str, QLabel] = {}
        self.setWindowTitle(tr("dialog.setup.title"))
        self.resize(980, 720)
        self._build_ui()
        if diagnostic is not None:
            self._show_diagnostic(diagnostic)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)
        layout.addWidget(self._build_hero())
        layout.addWidget(self._build_route_card())

        content = QGridLayout()
        content.setSpacing(14)
        self.security_card = self._build_security_card()
        content.addWidget(self.security_card, 0, 0, 2, 1)
        tiles = QGridLayout()
        tiles.setSpacing(12)
        for index, tile in enumerate(_tile_specs()):
            widget = self._build_tile(tile)
            tiles.addWidget(widget, index // 2, index % 2)
        content.addLayout(tiles, 0, 1, 2, 1)
        content.setColumnStretch(0, 5)
        content.setColumnStretch(1, 5)
        layout.addLayout(content, 1)

        self.summary = QLabel("")
        self.summary.setObjectName("StatusMessage")
        self.summary.setWordWrap(True)

        self.details = QLabel("")
        self.details.setTextFormat(Qt.TextFormat.RichText)
        self.details.setWordWrap(True)
        self.details.setObjectName("MutedLabel")
        self.details.setVisible(False)
        layout.addWidget(self.details)

        self.warning = QLabel("")
        self.warning.setObjectName("ChipWarning")
        self.warning.setWordWrap(True)
        self.warning.setVisible(False)
        layout.addWidget(self.warning)
        self.backup_progress_bar = QProgressBar()
        self.backup_progress_bar.setVisible(False)
        layout.addWidget(self.backup_progress_bar)

        buttons = QHBoxLayout()
        buttons.setSpacing(12)
        self.pick_other_button = _text_button(
            tr("dialog.setup.pick_other"),
            vendor_qicon("tabler", "folder-open", "success", 22),
            "success",
        )
        self.pick_other_button.clicked.connect(self.pick_route)
        buttons.addWidget(self.pick_other_button)
        self.details_action = _text_button(
            tr("dialog.setup.show_details"),
            vendor_qicon("tabler", "list", "default", 22),
            "default",
        )
        self.details_action.clicked.connect(self.toggle_details)
        buttons.addWidget(self.details_action)
        self.backup_button = _text_button(
            tr("dialog.setup.backup_sd"),
            vendor_qicon("tabler", "folder-open", "warning", 22),
            "warning",
        )
        self.backup_button.clicked.connect(self.backup_current_sd)
        self.backup_button.setVisible(False)
        buttons.addWidget(self.backup_button)
        self.skip_backup_button = _text_button(
            tr("dialog.setup.skip_backup"),
            vendor_qicon("tabler", "circle-x", "warning", 22),
            "warning",
        )
        self.skip_backup_button.clicked.connect(self.skip_backup_for_current_sd)
        self.skip_backup_button.setVisible(False)
        buttons.addWidget(self.skip_backup_button)
        buttons.addStretch(1)
        self.use_button = _text_button(tr("dialog.setup.use_path"), vendor_qicon("tabler", "circle-check", "success", 22), "success")
        self.use_button.clicked.connect(self.handle_primary_action)
        self.use_button.setEnabled(False)
        buttons.addWidget(self.use_button)
        close = QPushButton("")
        close.setIcon(vendor_qicon("tabler", "x", "default", 22))
        close.setIconSize(QSize(22, 22))
        close.setMinimumHeight(44)
        close.setMinimumWidth(52)
        close.setMaximumWidth(74)
        close.setProperty("variant", "default")
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.clicked.connect(self.reject)
        buttons.addWidget(close)
        layout.addLayout(buttons)

    def _build_hero(self) -> QWidget:
        hero = QWidget()
        hero.setObjectName("WizardHero")
        row = QHBoxLayout(hero)
        row.setContentsMargins(18, 16, 18, 16)
        icon = QLabel()
        icon.setFixedSize(76, 76)
        icon.setPixmap(app_logo_pixmap(72))
        icon.setStyleSheet("background: transparent;")
        row.addWidget(icon)
        text = QVBoxLayout()
        title = QLabel(tr("dialog.setup.heading"))
        title.setObjectName("WizardTitle")
        subtitle = QLabel(tr("dialog.setup.subtitle"))
        subtitle.setObjectName("WizardSubtitle")
        text.addWidget(title)
        text.addWidget(subtitle)
        row.addLayout(text, 1)
        sd_icon = QLabel()
        sd_icon.setFixedSize(66, 66)
        sd_icon.setPixmap(sd_card_qicon(62).pixmap(QSize(62, 62)))
        sd_icon.setStyleSheet("background: transparent;")
        row.addWidget(sd_icon)
        return hero

    def _build_route_card(self) -> QWidget:
        card = QWidget()
        card.setObjectName("RouteCard")
        grid = QGridLayout(card)
        grid.setContentsMargins(16, 14, 16, 14)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)
        sd = QLabel()
        sd.setFixedSize(58, 58)
        sd.setPixmap(sd_card_qicon(54).pixmap(QSize(54, 54)))
        sd.setStyleSheet("background: transparent;")
        grid.addWidget(sd, 0, 0, 2, 1, Qt.AlignmentFlag.AlignVCenter)
        self.route_title = QLabel(tr("dialog.setup.route_selection"))
        self.route_title.setObjectName("TileTitle")
        self.route_edit = QLineEdit(str(self.selected_path or ""))
        grid.addWidget(self.route_title, 0, 1)
        grid.addWidget(self.route_edit, 1, 1)
        browse = _text_button(tr("dialog.setup.browse"), vendor_qicon("tabler", "folder-open", "default", 22), "default")
        browse.clicked.connect(self.pick_route)
        grid.addWidget(browse, 1, 2)
        diagnose = _text_button(tr("dialog.setup.refresh"), vendor_qicon("tabler", "refresh", "accent", 22), "accent")
        diagnose.clicked.connect(self.run_diagnostic)
        grid.addWidget(diagnose, 1, 3)
        grid.setColumnStretch(1, 1)
        return card

    def _build_security_card(self) -> QWidget:
        card = QWidget()
        card.setObjectName("SecurityCard")
        row = QHBoxLayout(card)
        row.setContentsMargins(20, 20, 20, 20)
        row.setSpacing(18)
        self.security_icon = QLabel()
        self.security_icon.setObjectName("SecurityIcon")
        self.security_icon.setFixedSize(72, 72)
        self.security_icon.setStyleSheet("background: transparent; border: none;")
        row.addWidget(self.security_icon, 0, Qt.AlignmentFlag.AlignTop)
        text = QVBoxLayout()
        text.setSpacing(10)
        self.security_title = QLabel(tr("dialog.setup.diagnose_to_continue"))
        self.security_title.setObjectName("StatusTitle")
        self.security_title.setWordWrap(True)
        self.security_message = QLabel(tr("dialog.setup.select_sd"))
        self.security_message.setObjectName("StatusMessage")
        self.security_message.setWordWrap(True)
        text.addWidget(self.security_title)
        text.addWidget(self.security_message)
        text.addStretch(1)
        row.addLayout(text, 1)
        return card

    def _build_tile(self, spec: dict[str, str]) -> QWidget:
        tile = QWidget()
        tile.setObjectName("DiagnosticTile")
        layout = QVBoxLayout(tile)
        layout.setContentsMargins(14, 14, 14, 14)
        top = QHBoxLayout()
        icon = QLabel()
        icon_size = int(spec.get("icon_size", "38"))
        if spec.get("vendor_icon"):
            icon.setFixedSize(icon_size, icon_size)
            icon.setPixmap(
                vendor_qicon("tabler", spec["vendor_icon"], spec.get("variant", "default"), icon_size).pixmap(
                    QSize(icon_size, icon_size)
                )
            )
            icon.setStyleSheet("background: transparent;")
        else:
            icon.setFixedSize(icon_size, icon_size)
            icon.setPixmap(
                vendor_qicon("tabler", spec.get("icon", "alert-triangle"), spec.get("variant", "default"), icon_size).pixmap(
                    QSize(icon_size, icon_size)
                )
            )
        if spec.get("count_badge"):
            icon_holder = QWidget()
            icon_holder.setFixedSize(icon_size + 12, icon_size + 8)
            icon_holder.setStyleSheet("background: transparent;")
            stack = QStackedLayout(icon_holder)
            stack.setStackingMode(QStackedLayout.StackingMode.StackAll)
            stack.setContentsMargins(0, 0, 0, 0)
            icon_layer = QWidget()
            icon_layout = QHBoxLayout(icon_layer)
            icon_layout.setContentsMargins(0, 8, 12, 0)
            icon_layout.addWidget(icon, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)
            stack.addWidget(icon_layer)
            count_badge = QLabel("")
            count_badge.setMinimumSize(26, 24)
            count_badge.setMaximumHeight(24)
            count_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            count_badge.setObjectName("CountBadge")
            count_badge.setStyleSheet(
                "background: #5f6c75; color: #fffdf8; border: 1px solid #dfd4c6; "
                "border-radius: 12px; font-size: 8.5pt; font-weight: 800; padding: 0 5px;"
            )
            badge_layer = QWidget()
            badge_layout = QHBoxLayout(badge_layer)
            badge_layout.setContentsMargins(0, 0, 0, 0)
            badge_layout.addWidget(count_badge, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
            stack.addWidget(badge_layer)
            top.addWidget(icon_holder)
            self.tile_count_badges[spec["id"]] = count_badge
        else:
            icon.setStyleSheet("background: transparent;")
            top.addWidget(icon)
        top.addStretch(1)
        badge = QLabel()
        badge.setFixedSize(26, 26)
        badge.setStyleSheet("background: transparent;")
        top.addWidget(badge)
        layout.addLayout(top)
        title = QLabel(spec["title"])
        title.setObjectName("TileTitle")
        value = QLabel("-")
        value.setObjectName("TileValue")
        value.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(value)
        self.tile_widgets[spec["id"]] = tile
        self.tile_icons[spec["id"]] = badge
        self.tile_values[spec["id"]] = value
        return tile

    def toggle_details(self):
        if not self.details.text():
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(tr("dialog.setup.show_details"))
        dialog.resize(560, 420)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        title = QLabel(tr("dialog.setup.show_details"))
        title.setObjectName("StatusTitle")
        layout.addWidget(title)

        body = QLabel(self.details.text())
        body.setTextFormat(Qt.TextFormat.RichText)
        body.setWordWrap(True)
        body.setObjectName("MutedLabel")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addWidget(body)
        content_layout.addStretch(1)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        close = _text_button("Cerrar", vendor_qicon("tabler", "x", "default", 22), "default")
        close.clicked.connect(dialog.accept)
        buttons.addWidget(close)
        layout.addLayout(buttons)

        dialog.exec()

    def pick_route(self):
        folder = QFileDialog.getExistingDirectory(self, tr("toolbar.path_tooltip"), self.route_edit.text())
        if folder:
            self.route_edit.setText(folder)
            self.run_diagnostic()

    def run_diagnostic(self):
        path = Path(self.route_edit.text().strip())
        self.diagnostic = diagnose_storage(path)
        self.selected_path = path
        self._show_diagnostic(self.diagnostic)

    def _show_diagnostic(self, diagnostic: StorageDiagnostic):
        summary = diagnostic.summary
        self.route_edit.setText(str(diagnostic.root))
        severity = _diagnostic_severity(diagnostic)
        self.security_card.setObjectName(_security_card_name(severity))
        _refresh_style(self.security_card)
        self.security_title.setText(_diagnostic_title(diagnostic))
        self.security_message.setText(_diagnostic_message(diagnostic))
        self.security_icon.setPixmap(
            vendor_qicon("tabler", _security_icon(severity, diagnostic), _severity_variant(severity), 68).pixmap(QSize(68, 68))
        )
        self._update_tiles(diagnostic)
        detail_lines = [
            ("Ruta", str(diagnostic.root), True),
            ("Clasificacion", _route_class_label(diagnostic.route_class), False),
            ("Estado unidad", _health_label(diagnostic.storage_health), False),
            ("Menu", _menu_label(diagnostic.menu_state), False),
            ("Lectura permitida", "si" if diagnostic.scan_allowed else "no", False),
            ("Escritura permitida", "si" if diagnostic.write_allowed else "no", False),
        ]
        if summary is not None:
            detail_lines.extend([
                ("Dispositivo", _drive_type_label(summary.drive_type), False),
                ("Filesystem", summary.filesystem or "-", True),
                ("Carpetas numericas", str(len(summary.numeric_dirs)), True),
                ("Archivos/carpetas no GDEMU", str(len(summary.other_entries)), True),
            ])
            if summary.ignored_entries:
                detail_lines.append(("Archivos de sistema ignorados", str(len(summary.ignored_entries)), True))
        if diagnostic.menu is not None and diagnostic.menu.detail:
            detail_lines.append(("Detalle menu", diagnostic.menu.detail, False))
        self.details.setText(_format_detail_lines(detail_lines))
        self.details_action.setVisible(True)
        warnings = list(diagnostic.warnings)
        if diagnostic.prepare_allowed:
            warnings.append("Preparacion segura: solo se creara la base OpenMenu, no se copiaran juegos.")
        elif not diagnostic.write_allowed:
            warnings.append("Modo seguro: las acciones de escritura quedan bloqueadas.")
        self.warning.setText("\n".join(warnings))
        self.warning.setVisible(bool(warnings))
        decision = backup_decision(self.settings, diagnostic)
        show_backup = (
            _backup_recommended(diagnostic)
            and not registered_backup_exists(diagnostic.root)
            and (self.force_backup_prompt or not (decision and decision.get("decision") == "skipped"))
        )
        self.backup_button.setVisible(show_backup)
        self.backup_button.setEnabled(show_backup)
        self.skip_backup_button.setVisible(show_backup)
        self.skip_backup_button.setEnabled(show_backup)
        can_use = diagnostic.scan_allowed or diagnostic.write_allowed or diagnostic.prepare_allowed
        if diagnostic.prepare_allowed:
            self.use_button.setText(tr("dialog.setup.install_base"))
            self.use_button.setIcon(vendor_qicon("tabler", "device-floppy", "success", 22))
        else:
            self.use_button.setText(tr("dialog.setup.use_path"))
            self.use_button.setIcon(vendor_qicon("tabler", "circle-check", "success", 22))
        self.use_button.setVisible(can_use)
        self.use_button.setEnabled(can_use)

    def _update_tiles(self, diagnostic: StorageDiagnostic):
        for tile in _diagnostic_tiles(diagnostic):
            widget = self.tile_widgets[tile["id"]]
            widget.setObjectName(_tile_object_name(tile["severity"]))
            _refresh_style(widget)
            self.tile_values[tile["id"]].setText(tile["value"])
            badge_name = "circle-check" if tile["severity"] == "success" else "circle-x" if tile["severity"] == "danger" else "alert-triangle"
            status_badge = self.tile_icons[tile["id"]]
            if tile.get("hide_status_badge"):
                status_badge.clear()
                status_badge.setVisible(False)
            else:
                status_badge.setVisible(True)
                status_badge.setPixmap(
                    vendor_qicon("tabler", badge_name, _severity_variant(tile["severity"]), 24).pixmap(QSize(24, 24))
                )
            count_badge = self.tile_count_badges.get(tile["id"])
            if count_badge is not None:
                count_badge.setText(str(tile.get("count", "")))
                count_badge.setVisible(bool(tile.get("count", "")))

    def handle_primary_action(self):
        if self.diagnostic is not None and self.diagnostic.prepare_allowed:
            self.prepare_openmenu_base()
            return
        self.accept_selection()

    def prepare_openmenu_base(self):
        if self.diagnostic is None:
            self.run_diagnostic()
        if self.diagnostic is None or not self.diagnostic.prepare_allowed:
            return
        if not _confirm_dialog(
            self,
            tr("dialog.setup.install_confirm"),
        ):
            return
        try:
            self.diagnostic = install_openmenu_base(self.diagnostic.root, load_settings())
        except OpenMenuSetupError as exc:
            QMessageBox.warning(self, APP_NAME, str(exc))
            self.run_diagnostic()
            return
        self._show_diagnostic(self.diagnostic)
        if self.diagnostic.scan_allowed:
            self.selected_path = self.diagnostic.root
            self.accept()

    def accept_selection(self):
        if self.diagnostic is None:
            self.run_diagnostic()
        if self.diagnostic is None:
            return
        self.selected_path = self.diagnostic.root
        self.accept()

    def backup_current_sd(self):
        if self.diagnostic is None:
            self.run_diagnostic()
        if self.diagnostic is None:
            return
        default_target = suggested_backup_dir(self.diagnostic.root)
        folder = QFileDialog.getExistingDirectory(
            self,
            tr("dialog.backup.select_folder"),
            str(default_target.parent),
        )
        if not folder:
            return
        target = Path(folder)
        if target.name.lower() != default_target.name.lower():
            target = target / default_target.name
        if target.exists() and any(target.iterdir()):
            if not _confirm_dialog(
                self,
                tr("dialog.backup.folder_confirm", path=target),
            ):
                return
        if not _confirm_dialog(
            self,
            tr("dialog.backup.confirm", path=target),
        ):
            return
        self.backup_progress_bar.setVisible(True)
        self.backup_progress_bar.setRange(0, 0)
        self.use_button.setEnabled(False)
        self.backup_button.setEnabled(False)
        self.backup_worker = BackupWorker(self.diagnostic.root, target)
        self.backup_thread = QThread(self)
        self.backup_worker.moveToThread(self.backup_thread)
        self.backup_thread.started.connect(self.backup_worker.run)
        self.backup_worker.progress.connect(self.backup_progress)
        self.backup_worker.finished.connect(self.backup_finished)
        self.backup_worker.error.connect(self.backup_error)
        self.backup_worker.finished.connect(self.backup_thread.quit)
        self.backup_worker.error.connect(self.backup_thread.quit)
        self.backup_thread.finished.connect(self.backup_worker.deleteLater)
        self.backup_thread.finished.connect(self.backup_thread.deleteLater)
        self.backup_thread.start()

    def backup_progress(self, current: int, total: int, file_name: str):
        self.backup_progress_bar.setRange(0, total)
        self.backup_progress_bar.setValue(current)
        self.summary.setText(tr("dialog.backup.progress", current=current, total=total, file=file_name))

    def backup_finished(self, destination: str):
        self.backup_progress_bar.setVisible(False)
        self.use_button.setEnabled(True)
        self.backup_button.setEnabled(True)
        self.skip_backup_button.setVisible(False)
        if self.diagnostic is not None:
            self.settings = set_backup_decision(self.settings, self.diagnostic, "backed_up", Path(destination))
            write_backup_registry(self.diagnostic.root, Path(destination))
            save_settings(self.settings)
        QMessageBox.information(self, APP_NAME, tr("dialog.backup.done_detail", path=destination))
        self.summary.setText(tr("dialog.backup.done", path=destination))

    def backup_error(self, message: str):
        self.backup_progress_bar.setVisible(False)
        self.use_button.setEnabled(True)
        self.backup_button.setEnabled(True)
        QMessageBox.warning(self, APP_NAME, tr("dialog.backup.failed", message=message))

    def skip_backup_for_current_sd(self):
        if self.diagnostic is None:
            return
        if not _confirm_dialog(
            self,
            tr("dialog.backup.skip_confirm"),
        ):
            return
        self.settings = set_backup_decision(self.settings, self.diagnostic, "skipped")
        save_settings(self.settings)
        self.backup_button.setVisible(False)
        self.skip_backup_button.setVisible(False)
        self.summary.setText(tr("dialog.setup.backup_skipped"))


def _diagnostic_severity(diagnostic: StorageDiagnostic) -> str:
    if diagnostic.write_allowed:
        return "success"
    if diagnostic.prepare_allowed:
        return "warning"
    if diagnostic.scan_allowed:
        return "warning"
    return "danger"


def _confirm_dialog(parent: QWidget, text: str) -> bool:
    message = QMessageBox(parent)
    message.setWindowTitle(APP_NAME)
    message.setIcon(QMessageBox.Icon.Information)
    message.setText(text)
    continue_button = message.addButton(tr("dialog.backup.continue"), QMessageBox.ButtonRole.AcceptRole)
    cancel_button = message.addButton(tr("action.cancel"), QMessageBox.ButtonRole.RejectRole)
    message.setDefaultButton(cancel_button)
    message.exec()
    return message.clickedButton() is continue_button


def _backup_recommended(diagnostic: StorageDiagnostic) -> bool:
    summary = diagnostic.summary
    if summary is None:
        return False
    has_content = bool(summary.numeric_dirs or summary.other_entries)
    return has_content and diagnostic.route_class in {"gdemu_structure", "local_backup"} and diagnostic.scan_allowed


def _diagnostic_title(diagnostic: StorageDiagnostic) -> str:
    if diagnostic.write_allowed:
        return tr("dialog.setup.diagnostic.ready")
    if diagnostic.prepare_allowed:
        return tr("dialog.setup.diagnostic.empty_ready")
    if diagnostic.scan_allowed:
        return tr("dialog.setup.diagnostic.read_only")
    if diagnostic.route_class == "dangerous_path":
        return tr("dialog.setup.diagnostic.blocked")
    if diagnostic.storage_health == "not_fat32":
        return tr("dialog.setup.diagnostic.incompatible")
    if diagnostic.storage_health == "possible_corruption":
        return tr("dialog.setup.diagnostic.possible_corruption")
    return tr("dialog.setup.diagnostic.safety_block")


def _diagnostic_message(diagnostic: StorageDiagnostic) -> str:
    reason = diagnostic.reason.strip()
    if diagnostic.prepare_allowed:
        return (
            tr("dialog.setup.message.prepare")
        )
    if diagnostic.route_class == "dangerous_path":
        return (
            f"{reason}\n\n"
            + tr("dialog.setup.message.dangerous")
        )
    if diagnostic.storage_health == "not_fat32":
        return f"{reason}\n\n{tr('dialog.setup.message.not_fat32')}"
    if diagnostic.storage_health == "possible_corruption":
        return f"{reason}\n\n{tr('dialog.setup.message.possible_corruption')}"
    if not diagnostic.write_allowed and diagnostic.scan_allowed:
        return f"{reason}\n\n{tr('dialog.setup.message.scan_only')}"
    if diagnostic.write_allowed:
        return f"{reason}\n\n{tr('dialog.setup.message.write_allowed')}"
    return reason


def _status_card_name(severity: str) -> str:
    return {
        "success": "StatusCardSuccess",
        "warning": "StatusCardWarning",
        "danger": "StatusCardDanger",
    }.get(severity, "StatusCard")


def _security_card_name(severity: str) -> str:
    return {
        "success": "SecurityCardSuccess",
        "warning": "SecurityCard",
        "danger": "SecurityCardDanger",
    }.get(severity, "SecurityCard")


def _security_icon(severity: str, diagnostic: StorageDiagnostic) -> str:
    if diagnostic.prepare_allowed:
        return "device-floppy"
    if severity == "danger" or not diagnostic.write_allowed:
        return "lock"
    return {
        "success": "circle-check",
        "warning": "alert-triangle",
        "danger": "lock",
    }.get(severity, "alert-triangle")


def _severity_variant(severity: str) -> str:
    return {
        "success": "success",
        "warning": "warning",
        "danger": "danger",
    }.get(severity, "accent")


def _tile_specs() -> list[dict[str, str]]:
    return [
        {"id": "unit", "title": tr("dialog.setup.tile.unit"), "icon": "drive", "vendor_icon": "database", "icon_size": "58"},
        {"id": "filesystem", "title": tr("dialog.setup.tile.filesystem"), "icon": "filesystem", "vendor_icon": "cpu", "icon_size": "58"},
        {"id": "structure", "title": tr("dialog.setup.tile.structure"), "icon": "folder_tree", "vendor_icon": "hierarchy", "icon_size": "70"},
        {
            "id": "content",
            "title": tr("dialog.setup.tile.content"),
            "icon": "folder",
            "vendor_icon": "folders",
            "count_badge": "true",
            "icon_size": "64",
        },
    ]


def _diagnostic_tiles(diagnostic: StorageDiagnostic) -> list[dict[str, str]]:
    summary = diagnostic.summary
    filesystem = (summary.filesystem if summary else "") or "-"
    other_entries = len(summary.other_entries) if summary else 0
    numeric_dirs = len(summary.numeric_dirs) if summary else 0
    is_local_folder = bool(summary and summary.drive_type == "fixed" and not summary.is_root)

    unit_severity = "success" if diagnostic.storage_health in {"ok", "local_folder"} else "danger"
    if diagnostic.storage_health in {"not_fat32", "possible_corruption"}:
        unit_severity = "warning" if diagnostic.scan_allowed else "danger"

    fs_severity = "success"
    if is_local_folder:
        fs_value = tr("dialog.setup.value.local_folder_na")
    elif diagnostic.storage_health == "not_fat32":
        fs_severity = "danger"
        fs_value = tr("dialog.setup.value.detected", value=filesystem)
    elif filesystem not in {"-", ""} and filesystem.upper() != "FAT32":
        fs_severity = "warning"
        fs_value = tr("dialog.setup.value.detected", value=filesystem)
    else:
        fs_value = tr("dialog.setup.value.detected", value=filesystem) if filesystem != "-" else tr("dialog.setup.value.not_detected")

    if diagnostic.menu_state == "openmenu_compatible":
        structure_severity = "success"
    elif diagnostic.prepare_allowed:
        structure_severity = "warning"
    elif diagnostic.scan_allowed:
        structure_severity = "warning"
    else:
        structure_severity = "danger"

    content_severity = "success" if other_entries == 0 else "danger" if diagnostic.route_class == "dangerous_path" else "warning"

    return [
        {"id": "unit", "severity": unit_severity, "value": _health_label(diagnostic.storage_health)},
        {"id": "filesystem", "severity": fs_severity, "value": fs_value},
        {"id": "structure", "severity": structure_severity, "value": _menu_label(diagnostic.menu_state) if numeric_dirs else tr("dialog.setup.value.not_detected_f")},
        {
            "id": "content",
            "severity": content_severity,
            "value": tr("dialog.setup.value.files_found", count=other_entries),
            "count": other_entries,
        },
    ]


def _tile_object_name(severity: str) -> str:
    return {
        "success": "DiagnosticTileSuccess",
        "warning": "DiagnosticTileWarning",
        "danger": "DiagnosticTileDanger",
    }.get(severity, "DiagnosticTile")


def _refresh_style(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def _text_button(text: str, icon: QIcon, variant: str) -> QPushButton:
    button = QPushButton(text)
    button.setIcon(icon)
    button.setIconSize(QSize(22, 22))
    button.setMinimumHeight(44)
    button.setMinimumWidth(150)
    button.setProperty("variant", variant)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


def _format_detail_lines(lines: list[tuple[str, str, bool]]) -> str:
    rows: list[str] = []
    for label, value, code in lines:
        safe_label = escape(label)
        safe_value = escape(value)
        if code:
            value_html = (
                "<span style=\"font-family: Consolas, 'Courier New', monospace; "
                "background: rgba(0,0,0,0.04); padding: 1px 4px;\">"
                f"{safe_value}</span>"
            )
        else:
            value_html = safe_value
        rows.append(f"<div><b>{safe_label}:</b> {value_html}</div>")
    return "<div style=\"line-height: 1.35;\">" + "".join(rows) + "</div>"


def _route_class_label(value: str) -> str:
    return {
        "empty_safe": tr("dialog.setup.route.empty_safe"),
        "gdemu_structure": tr("dialog.setup.route.gdemu_structure"),
        "dangerous_path": tr("dialog.setup.route.dangerous_path"),
        "unknown": tr("dialog.setup.route.unknown"),
        "local_backup": tr("dialog.setup.route.local_backup"),
    }.get(value, value or "-")


def _health_label(value: str) -> str:
    return {
        "ok": tr("dialog.setup.health.ok"),
        "not_fat32": tr("dialog.setup.health.not_fat32"),
        "possible_corruption": tr("dialog.setup.health.possible_corruption"),
        "not_accessible": tr("dialog.setup.health.not_accessible"),
        "local_folder": tr("dialog.setup.health.local_folder"),
    }.get(value, value or "-")


def _menu_label(value: str) -> str:
    return {
        "openmenu_compatible": tr("dialog.setup.menu.openmenu_compatible"),
        "openmenu_old": tr("dialog.setup.menu.openmenu_old"),
        "gdmenu_basic": tr("dialog.setup.menu.gdmenu_basic"),
        "no_menu": tr("dialog.setup.menu.no_menu"),
        "unknown": tr("dialog.setup.value.not_detected"),
    }.get(value, value or "-")


def _drive_type_label(value: str) -> str:
    return {
        "removable": tr("dialog.setup.drive.removable"),
        "fixed": tr("dialog.setup.drive.fixed"),
        "network": tr("dialog.setup.drive.network"),
        "cdrom": "CD/DVD",
        "ramdisk": "RAM disk",
        "unknown": tr("dialog.setup.value.not_detected"),
    }.get(value, value or "-")

