"""Explicit presentation adapters for retained dialogs, including first-run UI.

Services and signal connections belong to the original dialogs. This registry
owns only their visual integration. Unregistered application dialogs are reported
by the coverage inventory, rather than silently counted as design-approved.
"""
from PySide6.QtCore import QObject, QEvent, QSize, Qt
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, QInputDialog, QLabel, QPushButton, QDialogButtonBox, QMessageBox, QTableWidget, QHeaderView

from ...i18n import tr
from . import design


RETAINED_DIALOGS = {
    'BackupPromptDialog': 'backup',
    'LegacyMenuUpgradeDialog': 'upgrade',
    'ConfirmApplyDialog': 'review',
    'ProviderSettingsDialog': 'providers',
    'ProviderConfigDialog': 'credentials',
    'LanguageSelectionDialog': 'language',
    'AboutDialog': 'about',
    'BulkProgressDialog': 'progress',
}

# Original translations are used as an exact binding, not an English substring
# heuristic. Parameters/unknown buttons retain their authored outline icon.
COMMAND_KEYS = {
    'action.cancel': ('x', 'secondary'),
    'action.close': ('x', 'secondary'),
    'action.save': ('device-floppy', 'primary'),
    'dialog.language.use': ('circle-check', 'primary'),
    'dialog.provider.configure': ('settings', 'secondary'),
    'dialog.provider.test': ('search', 'secondary'),
    'dialog.provider.signup': ('world', 'secondary'),
    'dialog.backup.choose': ('folder-open', 'secondary'),
    'dialog.backup.now': ('device-floppy', 'primary'),
    'dialog.backup.skip': ('arrow-right', 'secondary'),
    'legacy_upgrade.backup_first': ('folder-open', 'secondary'),
    'legacy_upgrade.update': ('refresh', 'primary'),
    'slot_recovery.complete': ('circle-check', 'primary'),
    'slot_recovery.revert': ('refresh', 'danger'),
    'slot_recovery.open_folder': ('folder-open', 'secondary'),
    'slot_recovery.later': ('x', 'secondary'),
    'scan_repair.save_now': ('device-floppy', 'primary'),
    'scan_repair.later': ('x', 'secondary'),
    'dialog.confirm_apply.repair_button': ('circle-check', 'primary'),
    'dialog.confirm_apply.covers_button': ('circle-check', 'primary'),
    'dialog.confirm_apply.apply_button': ('circle-check', 'primary'),
}


def refresh_button(button):
    glyph = button.property('v2Glyph')
    if not glyph:
        return
    c = design.colors()
    role = button.property('role')
    color = c['muted'] if not button.isEnabled() else c['paper'] if role == 'primary' else c['danger'] if role == 'danger' else c['ink']
    button.setIcon(design.icon(glyph, color))


def bind_button(button, glyph, role='secondary'):
    button.setProperty('v2Glyph', glyph)
    button.setProperty('role', role)
    button.setIconSize(QSize(design.METRICS['icon'], design.METRICS['icon']))
    button.setProperty('iconOnly', False)
    button.setMinimumWidth(0)
    button.setMaximumWidth(16777215)
    button.setMinimumHeight(design.METRICS['control-compact'])
    button.setMaximumHeight(16777215)
    button.setAccessibleName(button.text().replace('&', '') or tr('action.close'))
    button.setToolTip(button.accessibleName())
    # Legacy action_button paints its own stylesheet and fixed geometry.
    button.setStyleSheet('')
    refresh_button(button)
    design.repolish(button)


def _standard_button(dialog, button):
    # Button roles preserve behavior and safe default selection. Never reconnect.
    if isinstance(dialog, QMessageBox):
        role = dialog.buttonRole(button)
        standard = dialog.standardButton(button)
        if standard in (QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Close, QMessageBox.StandardButton.No):
            return 'x', 'secondary'
        if standard == QMessageBox.StandardButton.Discard:
            return 'trash', 'danger'
        if standard == QMessageBox.StandardButton.Save:
            return 'device-floppy', 'primary'
        if role == QMessageBox.ButtonRole.DestructiveRole:
            return 'trash', 'danger'
        if role in (QMessageBox.ButtonRole.AcceptRole, QMessageBox.ButtonRole.YesRole):
            return 'circle-check', 'primary'
    for box in dialog.findChildren(QDialogButtonBox):
        role = box.buttonRole(button)
        if role == QDialogButtonBox.ButtonRole.AcceptRole:
            return ('circle-check' if isinstance(dialog, QInputDialog) else 'device-floppy'), 'primary'
        if role == QDialogButtonBox.ButtonRole.RejectRole:
            return 'x', 'secondary'
    return None


def _translate_standard(dialog):
    if isinstance(dialog, QMessageBox):
        keys = {
            QMessageBox.StandardButton.Ok: 'action.ok',
            QMessageBox.StandardButton.Cancel: 'action.cancel',
            QMessageBox.StandardButton.Close: 'action.close',
            QMessageBox.StandardButton.Save: 'action.save',
            QMessageBox.StandardButton.Discard: 'action.discard',
            QMessageBox.StandardButton.Yes: 'action.yes',
            QMessageBox.StandardButton.No: 'action.no',
            QMessageBox.StandardButton.Retry: 'action.retry',
        }
        for standard, key in keys.items():
            button = dialog.button(standard)
            if button:
                button.setText(tr(key))
    elif isinstance(dialog, QInputDialog):
        dialog.setOkButtonText(tr('action.ok'))
        dialog.setCancelButtonText(tr('action.cancel'))


def adapt_dialog(dialog):
    kind = RETAINED_DIALOGS.get(type(dialog).__name__)
    if not kind and not isinstance(dialog, (QMessageBox, QInputDialog)):
        return False
    dialog.setProperty('v2Retained', True)
    _translate_standard(dialog)
    commands = {tr(key): value for key, value in COMMAND_KEYS.items()}
    for button in dialog.findChildren(QPushButton):
        spec = commands.get(button.text()) or _standard_button(dialog, button)
        if spec:
            bind_button(button, *spec)
        else:
            role = 'primary' if button.property('variant') in ('success', 'accent') else 'danger' if button.property('variant') == 'danger' else 'secondary'
            button.setProperty('role', role)
            button.setAccessibleName(button.text().replace('&', ''))
            design.repolish(button)
    if not kind or dialog.property('v2LayoutAdapted'):
        return True
    dialog.setProperty('v2LayoutAdapted', True)
    layout = dialog.layout()
    if layout:
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)
    for item in dialog.findChildren(QLabel):
        if item.objectName() in ('WizardTitle', 'StatusTitle', 'BusyTitle'):
            item.setProperty('heading', item.objectName() == 'WizardTitle')
            item.setProperty('title', item.objectName() != 'WizardTitle')
            item.setMinimumHeight(0)
            design.repolish(item)
        if item.objectName() in ('WizardSubtitle', 'MutedLabel', 'BusyDetail'):
            item.setProperty('muted', True)
            item.setMinimumHeight(0)
            design.repolish(item)
    if kind in ('backup', 'upgrade'):
        dialog.setMinimumSize(620, 300)
        dialog.resize(740, 420 if kind == 'backup' else 340)
        hero = dialog.findChild(QObject, 'WizardHero')
        if hero:
            hero.setMinimumHeight(0)
            hero.layout().setContentsMargins(12, 12, 12, 12)
            hero.layout().setSpacing(12)
            picture = next((item for item in hero.findChildren(QLabel) if not item.pixmap().isNull()), None)
            if picture:
                picture.setFixedSize(36, 36)
                picture.setPixmap(design.icon('folder-open' if kind == 'backup' else 'refresh', size=32).pixmap(32, 32))
        if kind == 'backup':
            # Choose destination is navigation, separate from backup/skip/cancel.
            chooser = dialog.choose_button
            for index in range(layout.count()):
                row = layout.itemAt(index).layout()
                if row and row.indexOf(chooser) >= 0:
                    row.removeWidget(chooser)
                    layout.insertWidget(index, chooser, 0, Qt.AlignmentFlag.AlignLeft)
                    break
            pictures = [item for item in dialog.findChildren(QLabel) if item.width() == 28 and not item.pixmap().isNull()]
            for item, glyph in zip(pictures, ('device-sd-card', 'folder-open')):
                item.setPixmap(design.icon(glyph).pixmap(24, 24))
    if kind == 'providers':
        dialog.setMinimumSize(620, 360)
        dialog.resize(920, 500)
        table = dialog.table
        table.setMinimumHeight(160)
        table.setAlternatingRowColors(False)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        # All seven columns remain accessible via horizontal scroll when needed.
        for col, width in ((0, 64), (2, 160), (3, 106), (4, 130), (5, 116), (6, 150)):
            table.setColumnWidth(col, width)
        for row in range(table.rowCount()):
            table.setRowHeight(row, 48)
    if kind == 'progress':
        dialog.setMinimumWidth(320)
        dialog.setMaximumWidth(16777215)
        bind_button(dialog.cancel_button, 'x')
        dialog.cancel_button.setText(tr('action.cancel'))
    return True


class DialogPresentation(QObject):
    def eventFilter(self, watched, event):
        if not QApplication.instance().property('v2Design'):
            return False
        if event.type() == QEvent.Type.Show and isinstance(watched, QDialog) and not isinstance(watched, QFileDialog):
            adapt_dialog(watched)
        elif event.type() == QEvent.Type.EnabledChange and isinstance(watched, QPushButton):
            refresh_button(watched)
        return False


def install(app):
    app.setProperty('v2Design', True)
    if not hasattr(app, '_v2_dialog_presentation'):
        app._v2_dialog_presentation = DialogPresentation(app)
        app.installEventFilter(app._v2_dialog_presentation)


def refresh_all(app):
    for widget in app.allWidgets():
        if isinstance(widget, QPushButton):
            refresh_button(widget)
