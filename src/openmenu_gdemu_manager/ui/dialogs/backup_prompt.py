from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QObject, QSize, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ... import APP_NAME
from ...config.settings import load_settings, save_settings
from ...dreamcast.storage_diagnostics import StorageDiagnostic
from ...i18n import tr
from ...services.backup_service import (
    BackupError,
    backup_sd_contents,
    set_backup_decision,
    suggested_backup_dir,
)
from ...services.sd_registry import write_backup_registry
from ..icons import illustration_pixmap, sd_card_qicon, vendor_qicon

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


class BackupPromptDialog(QDialog):
    """Explicit backup decision before enabling work on an existing SD."""

    def __init__(self, diagnostic: StorageDiagnostic, parent=None, force: bool = False):
        super().__init__(parent)
        self.diagnostic = diagnostic
        self.force = force
        self.settings = load_settings()
        self.destination = suggested_backup_dir(diagnostic.root)
        self.backup_thread: QThread | None = None
        self.backup_worker: BackupWorker | None = None
        self.setWindowTitle(tr("dialog.backup.title"))
        self.resize(840, 500)
        self.setMinimumSize(780, 460)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)

        hero = QWidget()
        hero.setObjectName("WizardHero")
        hero.setMinimumHeight(170)
        hero_row = QHBoxLayout(hero)
        hero_row.setContentsMargins(24, 22, 24, 22)
        hero_row.setSpacing(24)
        icon = QLabel()
        icon.setFixedSize(150, 126)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setPixmap(illustration_pixmap("backup_sd_to_hdd", 126))
        icon.setStyleSheet("background: transparent;")
        hero_row.addWidget(icon, 0, Qt.AlignmentFlag.AlignVCenter)

        text = QVBoxLayout()
        text.setSpacing(8)
        title = QLabel(tr("dialog.backup.heading"))
        title.setObjectName("WizardTitle")
        title.setWordWrap(True)
        title.setMinimumHeight(48)
        message = QLabel(tr("dialog.backup.message"))
        message.setObjectName("WizardSubtitle")
        message.setWordWrap(True)
        message.setMinimumHeight(56)
        message.setAlignment(Qt.AlignmentFlag.AlignTop)
        text.addWidget(title)
        text.addWidget(message)
        hero_row.addLayout(text, 1)
        layout.addWidget(hero)

        paths = QGridLayout()
        paths.setContentsMargins(0, 4, 0, 4)
        paths.setHorizontalSpacing(8)
        paths.setVerticalSpacing(14)
        paths.setColumnMinimumWidth(0, 34)
        paths.setColumnMinimumWidth(1, 170)
        paths.setColumnStretch(2, 1)

        _add_path_row(
            paths,
            0,
            sd_card_qicon(26).pixmap(QSize(26, 26)),
            tr("dialog.backup.source_label"),
            str(self.diagnostic.root),
        )

        self.destination_label = _add_path_row(
            paths,
            1,
            illustration_pixmap("drive_device", 26),
            tr("dialog.backup.destination_label"),
            str(self.destination),
        )
        layout.addLayout(paths)
        self._refresh_destination()

        warning = QLabel(tr("dialog.backup.warning"))
        warning.setObjectName("ChipWarning")
        warning.setWordWrap(True)
        layout.addWidget(warning)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)
        self.status = QLabel("")
        self.status.setObjectName("MutedLabel")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        self.choose_button = _button(tr("dialog.backup.choose"), "folder-open", "default")
        self.choose_button.clicked.connect(self.choose_destination)
        buttons.addWidget(self.choose_button)
        buttons.addStretch(1)
        self.skip_button = _button(tr("dialog.backup.skip"), "alert-triangle", "warning")
        self.skip_button.clicked.connect(self.skip_backup)
        buttons.addWidget(self.skip_button)
        self.backup_button = _button(tr("dialog.backup.now"), "device-floppy", "success")
        self.backup_button.clicked.connect(self.start_backup)
        buttons.addWidget(self.backup_button)
        cancel = _button(tr("action.cancel"), "x", "default")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)

    def _refresh_destination(self):
        self.destination_label.setText(str(self.destination))

    def choose_destination(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            tr("dialog.backup.select_folder"),
            str(self.destination.parent),
        )
        if not folder:
            return
        selected = Path(folder)
        default_name = suggested_backup_dir(self.diagnostic.root).name
        self.destination = selected if selected.name.lower() == default_name.lower() else selected / default_name
        self._refresh_destination()
        if self.destination.exists() and any(self.destination.iterdir()):
            QMessageBox.warning(
                self,
                APP_NAME,
                tr("dialog.backup.folder_has_data", path=self.destination),
            )

    def start_backup(self):
        if self.destination.exists() and any(self.destination.iterdir()):
            if not _confirm_message(
                self,
                tr("dialog.backup.folder_confirm", path=self.destination),
            ):
                return
        if not _confirm_message(
            self,
            tr("dialog.backup.confirm", path=self.destination),
        ):
            return
        self._set_busy(True, tr("dialog.backup.preparing"))
        self.backup_worker = BackupWorker(self.diagnostic.root, self.destination)
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
        self.progress.setRange(0, total)
        self.progress.setValue(current)
        self.status.setText(tr("dialog.backup.progress", current=current, total=total, file=file_name))

    def backup_finished(self, destination: str):
        self._set_busy(False, tr("dialog.backup.done", path=destination))
        self.settings = set_backup_decision(self.settings, self.diagnostic, "backed_up", Path(destination))
        write_backup_registry(self.diagnostic.root, Path(destination))
        save_settings(self.settings)
        QMessageBox.information(self, APP_NAME, tr("dialog.backup.done_detail", path=destination))
        self.accept()

    def backup_error(self, message: str):
        self._set_busy(False, "")
        QMessageBox.warning(self, APP_NAME, tr("dialog.backup.failed", message=message))

    def skip_backup(self):
        if not _confirm_message(self, tr("dialog.backup.skip_confirm")):
            return
        self.settings = set_backup_decision(self.settings, self.diagnostic, "skipped")
        save_settings(self.settings)
        self.accept()

    def _set_busy(self, busy: bool, message: str):
        self.progress.setVisible(busy)
        if busy:
            self.progress.setRange(0, 0)
        self.status.setText(message)
        self.choose_button.setEnabled(not busy)
        self.skip_button.setEnabled(not busy)
        self.backup_button.setEnabled(not busy)


def _button(text: str, icon_name: str, variant: str) -> QPushButton:
    button = QPushButton(text)
    button.setIcon(vendor_qicon("tabler", icon_name, variant, 22))
    button.setIconSize(QSize(22, 22))
    button.setMinimumHeight(44)
    button.setMinimumWidth(150)
    button.setProperty("variant", variant)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


def _confirm_message(parent: QWidget, text: str) -> bool:
    message = QMessageBox(parent)
    message.setWindowTitle(APP_NAME)
    message.setIcon(QMessageBox.Icon.Information)
    message.setText(text)
    continue_button = message.addButton(tr("dialog.backup.continue"), QMessageBox.ButtonRole.AcceptRole)
    cancel_button = message.addButton(tr("action.cancel"), QMessageBox.ButtonRole.RejectRole)
    message.setDefaultButton(cancel_button)
    message.exec()
    return message.clickedButton() is continue_button


def _add_path_row(grid: QGridLayout, row: int, icon_pixmap, label_text: str, value_text: str) -> QLabel:
    icon = QLabel()
    icon.setFixedSize(28, 28)
    icon.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
    icon.setPixmap(icon_pixmap)
    icon.setStyleSheet("background: transparent;")
    grid.addWidget(icon, row, 0, Qt.AlignmentFlag.AlignTop)

    label = QLabel(label_text)
    label.setObjectName("PathLabel")
    label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
    label.setStyleSheet("background: transparent; font-weight: 800;")
    grid.addWidget(label, row, 1, Qt.AlignmentFlag.AlignTop)

    value = QLabel(value_text)
    value.setObjectName("StatusMessage")
    value.setWordWrap(True)
    value.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
    grid.addWidget(value, row, 2)
    return value
