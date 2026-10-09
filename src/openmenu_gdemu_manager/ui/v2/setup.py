"""Compact destination guidance over the original setup and backup services."""
from pathlib import Path

import shiboken6
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLineEdit, QMessageBox, QProgressBar, QScrollArea, QVBoxLayout

from ...config.settings import load_settings
from ...dreamcast.storage_diagnostics import diagnose_storage
from ...services.setup_service import install_openmenu_base, OpenMenuSetupError
from ...i18n import tr as app_tr
from ..dialogs.setup_wizard import SetupWizardDialog, _confirm_dialog, _setup_error_text, _diagnostic_tiles
from . import design
from .catalog import tr
from .design import Button, box, label, repolish


class SetupWizardV2(SetupWizardDialog):
    """Retain decisions/services, replace presentation and stale-path handling."""

    def __init__(self, diagnostic=None, parent=None, force_backup_prompt=False):
        self._rendering = False
        self._backup_active = False
        self._installed = False
        super().__init__(diagnostic, parent, force_backup_prompt)
        self.resize(720, 500)
        if diagnostic is None:
            self._show_unselected()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)
        root.addWidget(label(tr('setup_heading'), heading=True))
        root.addWidget(label(tr('setup_intro'), muted=True, wrap=True))
        route = QHBoxLayout()
        self.route_edit = QLineEdit(str(self.selected_path or ''))
        self.route_edit.setPlaceholderText(tr('setup_path_hint'))
        self.route_edit.setAccessibleName(tr('setup_path_hint'))
        route.addWidget(self.route_edit, 1)
        self.pick_other_button = Button('browse', self.pick_route)
        route.addWidget(self.pick_other_button)
        self.refresh_button = Button('scan', self.run_diagnostic, text=tr('setup_validate'))
        route.addWidget(self.refresh_button)
        root.addLayout(route)
        self.route_edit.textEdited.connect(self._route_edited)
        self.route_edit.returnPressed.connect(self.run_diagnostic)
        self.security_card, status = box(margins=12, spacing=6, name='Card')
        self.security_title = label('', title=True, wrap=True)
        # Legacy diagnostic controller still sets this icon; it is not shown.
        self.security_icon = label('')
        self.security_message = label('', wrap=True)
        status.addWidget(self.security_title)
        status.addWidget(self.security_message)
        root.addWidget(self.security_card)
        self.warning = label('', tone='warning', wrap=True)
        root.addWidget(self.warning)
        self.summary = label('', wrap=True)
        root.addWidget(self.summary)
        self.details_action = Button('info', self.toggle_details, text=app_tr('dialog.setup.show_details'), compact=True)
        self.details_action.setCheckable(True)
        root.addWidget(self.details_action, 0, Qt.AlignmentFlag.AlignLeft)
        self.details = label('', wrap=True)
        self.details.setTextFormat(Qt.TextFormat.RichText)
        self.details_scroll = QScrollArea()
        self.details_scroll.setWidgetResizable(True)
        self.details_scroll.setMinimumHeight(80)
        self.details_scroll.setWidget(self.details)
        self.details_scroll.hide()
        root.addWidget(self.details_scroll, 1)
        root.addStretch(1)
        self.backup_progress_bar = QProgressBar()
        self.backup_progress_bar.hide()
        root.addWidget(self.backup_progress_bar)
        # Backup choices occupy their own row; the footer never grows to six buttons.
        backup = QHBoxLayout()
        self.backup_button = Button('browse', self.backup_current_sd, text=app_tr('dialog.setup.backup_sd'))
        self.skip_backup_button = Button('cancel', self.skip_backup_for_current_sd, text=app_tr('dialog.setup.skip_backup'))
        for button in (self.backup_button, self.skip_backup_button):
            button.hide()
            backup.addWidget(button)
        backup.addStretch(1)
        root.addLayout(backup)
        footer = QHBoxLayout()
        footer.addStretch(1)
        self.cancel_button = Button('cancel', self.reject)
        footer.addWidget(self.cancel_button)
        self.use_button = Button('select', self.handle_primary_action, text=app_tr('dialog.setup.use_path'))
        self.use_button.hide()
        footer.addWidget(self.use_button)
        root.addLayout(footer)

    def _show_unselected(self):
        self.security_title.setText(tr('setup_choose_title'))
        self.security_message.setText(tr('setup_choose_body'))
        self.warning.hide()
        self.summary.hide()
        self.details_action.hide()
        self.details_scroll.hide()
        self.details_action.setChecked(False)
        self.use_button.hide()
        self.backup_button.hide()
        self.skip_backup_button.hide()
        self.refresh_button.setEnabled(bool(self.route_edit.text().strip()))
        self._browse_role('primary')

    def _browse_role(self, role):
        self.pick_other_button.setProperty('role', role)
        self.pick_other_button.refresh_icon()
        repolish(self.pick_other_button)

    def _route_edited(self, _text):
        if self._rendering:
            return
        self.diagnostic = None
        self.selected_path = None
        self._installed = False
        self._show_unselected()

    def run_diagnostic(self):
        if self._backup_active or not self.route_edit.text().strip():
            return
        self.diagnostic = diagnose_storage(Path(self.route_edit.text().strip()))
        self.selected_path = self.diagnostic.root
        self._show_diagnostic(self.diagnostic)

    def _show_diagnostic(self, diagnostic):
        self._rendering = True
        try:
            super()._show_diagnostic(diagnostic)
        finally:
            self._rendering = False
        self.details.setText(self._diagnostic_rows + '<br>' + self.details.text())
        # status cards use semantic properties, never legacy object-name variants.
        self.security_card.setObjectName('Card')
        self.security_message.setText(self.security_message.text().strip().replace('\n\n', '\n'))
        tone = 'success' if diagnostic.write_allowed else 'warning' if diagnostic.scan_allowed or diagnostic.prepare_allowed else 'danger'
        self.security_title.setProperty('tone', tone)
        repolish(self.security_title)
        self.warning.setVisible(bool(self.warning.text()))
        self.summary.setVisible(bool(self.summary.text()))
        self.refresh_button.setEnabled(True)
        self._browse_role('secondary' if self.use_button.isVisibleTo(self) else 'primary')
        if diagnostic.prepare_allowed:
            self.use_button.action = 'install_template'
            self.use_button.setText(app_tr('dialog.setup.install_base'))
        else:
            self.use_button.action = 'select'
        self.use_button.refresh_icon()
        self.use_button.setDefault(bool(diagnostic.scan_allowed or diagnostic.prepare_allowed or diagnostic.write_allowed))

    def _update_tiles(self, diagnostic):
        # Accessible compact text in the technical disclosure. N/A is neutral.
        from html import escape
        rows = []
        for tile in _diagnostic_tiles(diagnostic):
            key = tile['id']
            title = app_tr('dialog.setup.tile.' + key)
            rows.append(f'<div><b>{escape(title)}:</b> {escape(tile["value"])}</div>')
        self._diagnostic_rows = ''.join(rows)

    def toggle_details(self):
        opened = self.details_action.isChecked()
        self.details_scroll.setVisible(opened)
        self.details_action.setText(app_tr('dialog.setup.hide_details' if opened else 'dialog.setup.show_details'))

    def handle_primary_action(self):
        if self._backup_active:
            return
        if self._installed:
            self.accept_selection()
            return
        # Always diagnose the currently displayed path, even after programmatic edits.
        self.run_diagnostic()
        if self.diagnostic is None:
            return
        if self.diagnostic.prepare_allowed:
            self.prepare_openmenu_base()
        elif self.diagnostic.scan_allowed or self.diagnostic.write_allowed:
            self.accept_selection()

    def accept_selection(self):
        if self._backup_active:
            return
        self.run_diagnostic()
        if self.diagnostic and (self.diagnostic.scan_allowed or self.diagnostic.write_allowed):
            self.selected_path = self.diagnostic.root
            QDialog.accept(self)

    def prepare_openmenu_base(self):
        if not self.diagnostic or not self.diagnostic.prepare_allowed or self._backup_active:
            return
        if not _confirm_dialog(self, app_tr('dialog.setup.install_confirm'), app_tr('dialog.setup.install_action')):
            return
        # Services revalidate internally. Keep the outcome visible until Continue.
        try:
            result = install_openmenu_base(self.diagnostic.root, load_settings())
        except (OpenMenuSetupError, OSError) as exc:
            QMessageBox.warning(self, self.windowTitle(), _setup_error_text(exc) if isinstance(exc, OpenMenuSetupError) else str(exc))
            self.run_diagnostic()
            return
        self.diagnostic = result
        self.selected_path = result.root
        self._show_diagnostic(result)
        self._installed = bool(result.scan_allowed)
        if self._installed:
            self.security_title.setText(tr('setup_installed_title'))
            self.security_message.setText(tr('setup_installed_body'))
            self.use_button.setText(tr('setup_continue'))

    def backup_current_sd(self):
        if self._backup_active:
            return
        super().backup_current_sd()
        thread = self.backup_thread
        if thread is not None and shiboken6.isValid(thread) and thread.isRunning():
            self._backup_active = True
            for widget in (self.route_edit, self.pick_other_button, self.refresh_button, self.skip_backup_button, self.cancel_button):
                widget.setEnabled(False)
            thread.finished.connect(self._backup_stopped)

    def _backup_stopped(self):
        self._backup_active = False
        self.backup_thread = None
        self.backup_worker = None
        for widget in (self.route_edit, self.pick_other_button, self.refresh_button, self.skip_backup_button, self.cancel_button):
            widget.setEnabled(True)
        if self.diagnostic:
            self._show_diagnostic(self.diagnostic)

    def reject(self):
        if not self._backup_active:
            super().reject()

    def closeEvent(self, event):
        if self._backup_active:
            event.ignore()
        else:
            super().closeEvent(event)
