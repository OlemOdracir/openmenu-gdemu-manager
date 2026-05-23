from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ...i18n import tr
from ..icons import vendor_qicon


class LegacyMenuUpgradeDialog(QDialog):
    ACTION_BACKUP = "backup"
    ACTION_UPDATE = "update"

    def __init__(self, has_registered_backup: bool, parent=None):
        super().__init__(parent)
        self.has_registered_backup = has_registered_backup
        self.selected_action = ""
        self.setWindowTitle(tr("legacy_upgrade.title"))
        self.resize(760, 360)
        self.setMinimumSize(700, 320)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 24, 26, 24)
        layout.setSpacing(16)

        hero = QWidget()
        hero.setObjectName("WizardHero")
        row = QHBoxLayout(hero)
        row.setContentsMargins(24, 22, 24, 22)
        row.setSpacing(22)

        icon = QLabel()
        icon.setFixedSize(82, 82)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setPixmap(vendor_qicon("tabler", "refresh", "warning", 64).pixmap(QSize(64, 64)))
        icon.setStyleSheet("background: transparent;")
        row.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)

        text_col = QVBoxLayout()
        text_col.setSpacing(10)
        title = QLabel(tr("legacy_upgrade.heading"))
        title.setObjectName("WizardTitle")
        title.setWordWrap(True)
        body = QLabel(tr("legacy_upgrade.body"))
        body.setObjectName("WizardSubtitle")
        body.setWordWrap(True)
        text_col.addWidget(title)
        text_col.addWidget(body)
        row.addLayout(text_col, 1)
        layout.addWidget(hero)

        if not self.has_registered_backup:
            warning = QLabel(tr("legacy_upgrade.no_backup_warning"))
            warning.setObjectName("ChipWarning")
            warning.setWordWrap(True)
            layout.addWidget(warning)

        layout.addStretch(1)
        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        buttons.addStretch(1)
        if not self.has_registered_backup:
            self.backup_button = _button(tr("legacy_upgrade.backup_first"), "folder-open", "warning")
            self.backup_button.clicked.connect(self._backup_first)
            buttons.addWidget(self.backup_button)
        self.update_button = _button(tr("legacy_upgrade.update"), "refresh", "success")
        self.update_button.clicked.connect(self._update)
        buttons.addWidget(self.update_button)
        cancel = _button(tr("action.cancel"), "x", "default")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)

    def _backup_first(self):
        self.selected_action = self.ACTION_BACKUP
        self.accept()

    def _update(self):
        self.selected_action = self.ACTION_UPDATE
        self.accept()


def _button(text: str, icon_name: str, variant: str) -> QPushButton:
    button = QPushButton(text)
    button.setIcon(vendor_qicon("tabler", icon_name, variant, 22))
    button.setIconSize(QSize(22, 22))
    button.setMinimumHeight(46)
    button.setMinimumWidth(160)
    button.setProperty("variant", variant)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button
