from __future__ import annotations

import copy
import webbrowser

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...config.settings import save_settings
from ...covers.providers.registry import provider_definitions, test_provider
from ...i18n import tr
from ..widgets import apply_interactive_cursor


class ProviderSettingsDialog(QDialog):
    HEADER_KEYS = [
        "dialog.provider.active",
        "dialog.provider.name",
        "table.status",
        "dialog.provider.priority",
        "dialog.provider.configure",
        "dialog.provider.test",
        "dialog.provider.signup",
    ]

    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("dialog.provider.title"))
        self.resize(1120, 540)
        self.settings = copy.deepcopy(settings)
        self.definitions = provider_definitions()
        self.rows: dict[str, int] = {}
        self.enabled_widgets: dict[str, QCheckBox] = {}
        self.priority_widgets: dict[str, QSpinBox] = {}
        self.status_items: dict[str, QTableWidgetItem] = {}
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        intro = QLabel(tr("dialog.provider.intro"))
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.table = QTableWidget(len(self.definitions), len(self.HEADER_KEYS), self)
        self.table.setHorizontalHeaderLabels([tr(key) for key in self.HEADER_KEYS])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setMinimumHeight(360)
        self.table.setWordWrap(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setStretchLastSection(False)
        layout.addWidget(self.table, 1)

        for row, (provider_id, definition) in enumerate(self.definitions.items()):
            self.rows[provider_id] = row
            cfg = self.settings.setdefault("cover_providers", {}).setdefault(provider_id, {})
            if definition.coming_soon:
                cfg["enabled"] = False

            enabled = QCheckBox()
            enabled.setChecked(bool(cfg.get("enabled", False)))
            enabled.setEnabled(not definition.coming_soon)
            apply_interactive_cursor(enabled)
            enabled.stateChanged.connect(lambda _state, pid=provider_id: self._sync_row(pid))
            self.enabled_widgets[provider_id] = enabled
            self.table.setCellWidget(row, 0, _centered(enabled))

            self.table.setItem(row, 1, QTableWidgetItem(definition.label))

            status_item = QTableWidgetItem(self._status_text(provider_id))
            status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.status_items[provider_id] = status_item
            self.table.setItem(row, 2, status_item)

            priority = QSpinBox()
            priority.setRange(1, 999)
            priority.setValue(int(cfg.get("priority", 999) or 999))
            priority.setMinimumWidth(92)
            priority.valueChanged.connect(lambda _value, pid=provider_id: self._sync_row(pid))
            self.priority_widgets[provider_id] = priority
            self.table.setCellWidget(row, 3, priority)

            config_btn = QPushButton(tr("dialog.provider.configure"))
            config_btn.setMinimumWidth(112)
            config_btn.setEnabled(definition.configurable and not definition.coming_soon)
            apply_interactive_cursor(config_btn)
            config_btn.clicked.connect(lambda _=False, pid=provider_id: self._configure(pid))
            self.table.setCellWidget(row, 4, config_btn)

            test_btn = QPushButton(tr("dialog.provider.test"))
            test_btn.setMinimumWidth(92)
            test_btn.setEnabled(not definition.coming_soon)
            apply_interactive_cursor(test_btn)
            test_btn.clicked.connect(lambda _=False, pid=provider_id: self._test(pid))
            self.table.setCellWidget(row, 5, test_btn)

            signup_btn = QPushButton(tr("dialog.provider.signup"))
            signup_btn.setMinimumWidth(112)
            signup_btn.setEnabled(bool(definition.signup_url) and not definition.coming_soon)
            apply_interactive_cursor(signup_btn)
            signup_btn.clicked.connect(lambda _=False, pid=provider_id: self._signup(pid))
            self.table.setCellWidget(row, 6, signup_btn)

        self._apply_table_layout()

        buttons = QDialogButtonBox()
        save_button = buttons.addButton(tr("action.save"), QDialogButtonBox.ButtonRole.AcceptRole)
        cancel_button = buttons.addButton(tr("action.cancel"), QDialogButtonBox.ButtonRole.RejectRole)
        save_button.setMinimumWidth(110)
        cancel_button.setMinimumWidth(110)
        apply_interactive_cursor(save_button)
        apply_interactive_cursor(cancel_button)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _apply_table_layout(self):
        widths = [82, 230, 185, 120, 130, 110, 140]
        for column, width in enumerate(widths):
            self.table.setColumnWidth(column, width)
        for row in range(self.table.rowCount()):
            self.table.setRowHeight(row, 42)

    def accept(self):
        for provider_id in self.definitions:
            self._sync_row(provider_id)
        legacy = self.settings.setdefault("providers", {})
        for provider_id in ("local", "openmenu", "libretro"):
            legacy[provider_id] = bool(self.settings["cover_providers"].get(provider_id, {}).get("enabled", False))
        save_settings(self.settings)
        super().accept()

    def _sync_row(self, provider_id: str):
        cfg = self.settings.setdefault("cover_providers", {}).setdefault(provider_id, {})
        cfg["enabled"] = self.enabled_widgets[provider_id].isChecked()
        cfg["priority"] = self.priority_widgets[provider_id].value()
        if provider_id in self.status_items:
            self.status_items[provider_id].setText(self._status_text(provider_id))

    def _status_text(self, provider_id: str) -> str:
        cfg = self.settings.get("cover_providers", {}).get(provider_id, {})
        definition = self.definitions[provider_id]
        if not cfg.get("enabled", False):
            if definition.coming_soon:
                return tr("dialog.provider.status.coming_soon")
            return tr("dialog.provider.status.disabled")
        if definition.find is None:
            return tr("dialog.provider.status.reserved")
        if definition.requires_credentials and not _has_credentials(provider_id, cfg):
            return tr("dialog.provider.status.missing_credentials")
        return tr("dialog.provider.status.active")

    def _configure(self, provider_id: str):
        dialog = ProviderConfigDialog(provider_id, self.definitions[provider_id].label, self.settings, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            cfg = self.settings.setdefault("cover_providers", {}).setdefault(provider_id, {})
            cfg.update(dialog.values())
            if "enabled" in dialog.values():
                self.enabled_widgets[provider_id].setChecked(bool(dialog.values()["enabled"]))
            if "priority" in dialog.values():
                self.priority_widgets[provider_id].setValue(int(dialog.values()["priority"] or 999))
            self._sync_row(provider_id)

    def _test(self, provider_id: str):
        self._sync_row(provider_id)
        result = test_provider(provider_id, self.settings)
        self.status_items[provider_id].setText(tr("dialog.provider.status.ok") if result.get("ok") else tr("status.error"))
        title = tr("dialog.provider.test_ok") if result.get("ok") else tr("dialog.provider.test_failed")
        QMessageBox.information(self, title, str(result.get("message", "")))

    def _signup(self, provider_id: str):
        url = self.definitions[provider_id].signup_url
        if url:
            webbrowser.open(url)


class ProviderConfigDialog(QDialog):
    FIELD_MAP = {
        "screenscraper": [
            ("enabled", "Activo", "bool"),
            ("ssid", "Usuario ScreenScraper", "text"),
            ("sspassword", "Password ScreenScraper", "password"),
            ("timeout", "Timeout", "int"),
            ("priority", "Prioridad", "int"),
            ("min_auto_score", "Score auto", "int"),
            ("min_review_score", "Score revision", "int"),
        ],
        "default": [
            ("enabled", "Activo", "bool"),
            ("base_url", "Base URL", "text"),
            ("api_key", "API key", "password"),
            ("client_id", "Client ID", "text"),
            ("client_secret", "Client secret", "password"),
            ("priority", "Prioridad", "int"),
            ("min_auto_score", "Score auto", "int"),
            ("min_review_score", "Score revision", "int"),
        ],
    }

    def __init__(self, provider_id: str, label: str, settings: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("dialog.provider.configure_title", name=label))
        self.provider_id = provider_id
        self.cfg = copy.deepcopy(settings.get("cover_providers", {}).get(provider_id, {}))
        self.inputs: dict[str, object] = {}
        self._values: dict = {}
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        fields = self.FIELD_MAP.get(self.provider_id, self.FIELD_MAP["default"])
        for key, label, kind in fields:
            if key not in self.cfg and kind != "bool":
                continue
            if kind == "bool":
                widget = QCheckBox()
                widget.setChecked(bool(self.cfg.get(key, False)))
                apply_interactive_cursor(widget)
            elif kind == "int":
                widget = QSpinBox()
                widget.setRange(0, 999)
                widget.setValue(int(self.cfg.get(key, 0) or 0))
            else:
                widget = QLineEdit(str(self.cfg.get(key, "")))
                if kind == "password":
                    widget.setEchoMode(QLineEdit.EchoMode.Password)
            self.inputs[key] = widget
            form.addRow(label, widget)
        layout.addLayout(form)
        buttons = QDialogButtonBox()
        save_button = buttons.addButton(tr("action.save"), QDialogButtonBox.ButtonRole.AcceptRole)
        cancel_button = buttons.addButton(tr("action.cancel"), QDialogButtonBox.ButtonRole.RejectRole)
        apply_interactive_cursor(save_button)
        apply_interactive_cursor(cancel_button)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self):
        for key, widget in self.inputs.items():
            if isinstance(widget, QCheckBox):
                self._values[key] = widget.isChecked()
            elif isinstance(widget, QSpinBox):
                self._values[key] = widget.value()
            elif isinstance(widget, QLineEdit):
                self._values[key] = widget.text().strip()
        super().accept()

    def values(self) -> dict:
        return dict(self._values)


def _centered(widget: QWidget) -> QWidget:
    holder = QWidget()
    layout = QHBoxLayout(holder)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(widget, 0, Qt.AlignmentFlag.AlignCenter)
    return holder


def _has_credentials(provider_id: str, cfg: dict) -> bool:
    if provider_id == "screenscraper":
        return all(str(cfg.get(key, "")).strip() for key in ("ssid", "sspassword"))
    if provider_id == "igdb":
        return all(str(cfg.get(key, "")).strip() for key in ("client_id", "client_secret"))
    return bool(str(cfg.get("api_key", "")).strip())
