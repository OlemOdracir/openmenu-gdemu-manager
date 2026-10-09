"""Retained-dialog design coverage, not merely presence of controller methods."""
from pathlib import Path
import os

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QPushButton, QMessageBox, QInputDialog, QLabel, QTableWidget

from openmenu_gdemu_manager.i18n import set_language, active_language, available_languages
from openmenu_gdemu_manager.dreamcast.storage_diagnostics import diagnose_storage
from openmenu_gdemu_manager.ui.v2 import design, setup
from openmenu_gdemu_manager.ui.v2.retained_dialogs import RETAINED_DIALOGS
from openmenu_gdemu_manager.ui.dialogs import backup_prompt
from openmenu_gdemu_manager.ui.dialogs.legacy_upgrade import LegacyMenuUpgradeDialog
from openmenu_gdemu_manager.ui.dialogs.confirm_apply import ConfirmApplyDialog
from openmenu_gdemu_manager.ui.dialogs.provider_settings import ProviderSettingsDialog, ProviderConfigDialog
from openmenu_gdemu_manager.ui.dialogs.language_selection import LanguageSelectionDialog
from openmenu_gdemu_manager.ui.dialogs.about import AboutDialog
from openmenu_gdemu_manager.ui.dialogs.bulk_progress import BulkProgressDialog


@pytest.fixture
def app():
    instance = QApplication.instance() or QApplication([])
    previous = active_language()
    set_language('es')
    design.apply_theme(instance)
    yield instance
    set_language(previous)


def _show(app, dialog, size=None):
    if size:
        dialog.resize(*size)
    dialog.show()
    app.processEvents()
    return dialog


def _dispose(app, dialog):
    if isinstance(dialog, BulkProgressDialog):
        dialog.spinner.stop()
        dialog.accept()
    else:
        dialog.hide()
    dialog.deleteLater()
    app.processEvents()


def _capture(dialog, name):
    folder = os.environ.get('OPENMENU_V2_CAPTURE_DIR')
    if folder:
        target = Path(folder)
        target.mkdir(parents=True, exist_ok=True)
        assert dialog.grab().save(str(target / (name + '.png')))


def _visible_buttons_reachable(dialog):
    for button in dialog.findChildren(QPushButton):
        if not button.isVisibleTo(dialog):
            continue
        assert button.accessibleName(), (type(dialog).__name__, button.text())
        if any(table.isAncestorOf(button) for table in dialog.findChildren(QTableWidget)):
            # Table cells are intentionally scrollable, unlike the fixed footer.
            continue
        point = button.mapTo(dialog, button.rect().bottomRight())
        assert dialog.rect().contains(point), (type(dialog).__name__, button.text(), point, dialog.size())


@pytest.mark.parametrize('size', [(640, 420), (720, 500), (900, 620)])
@pytest.mark.parametrize('state', ['choose', 'empty', 'blocked', 'readonly', 'ready'])
def test_setup_states_hierarchy_disclosure_and_footer(app, tmp_path, size, state):
    destination = tmp_path / 'destination'
    destination.mkdir()
    if state == 'blocked':
        (destination / 'personal.txt').write_text('unrelated content')
    diagnostic = None if state == 'choose' else diagnose_storage(destination)
    if state in ('readonly', 'ready'):
        diagnostic.prepare_allowed = False
        diagnostic.scan_allowed = True
        diagnostic.write_allowed = state == 'ready'
        diagnostic.menu_state = 'openmenu_compatible' if state == 'ready' else 'gdmenu_basic'
    dialog = _show(app, setup.SetupWizardV2(diagnostic), size)
    assert dialog.security_card.objectName() == 'Card'
    assert not dialog.details_scroll.isVisible()
    assert dialog.security_title.text() and dialog.security_message.text()
    assert dialog.use_button.isVisible() == (state in ('empty', 'readonly', 'ready'))
    assert dialog.pick_other_button.property('role') == ('primary' if state in ('choose', 'blocked') else 'secondary')
    _visible_buttons_reachable(dialog)
    _capture(dialog, f'setup-{state}-{size[0]}x{size[1]}')
    if state != 'choose':
        QTest.mouseClick(dialog.details_action, Qt.MouseButton.LeftButton)
        app.processEvents()
        assert dialog.details_scroll.isVisible()
        _visible_buttons_reachable(dialog)
        assert not any(not item.pixmap().isNull() for item in dialog.details_scroll.findChildren(QLabel))
        _capture(dialog, f'setup-{state}-details-{size[0]}x{size[1]}')
    _dispose(app, dialog)


def test_setup_revalidates_edited_path_and_blocks_stale_acceptance(app, tmp_path, monkeypatch):
    source = tmp_path / 'empty'
    source.mkdir()
    blocked = tmp_path / 'blocked'
    blocked.mkdir()
    (blocked / 'personal.txt').write_text('keep')
    dialog = setup.SetupWizardV2(diagnose_storage(source))
    calls = []
    monkeypatch.setattr(setup, 'install_openmenu_base', lambda *args: calls.append(args))
    dialog.route_edit.setText(str(blocked))
    dialog.handle_primary_action()
    assert not calls and dialog.result() != QDialog.DialogCode.Accepted
    assert dialog.diagnostic.root == blocked and not dialog.diagnostic.prepare_allowed
    assert (blocked / 'personal.txt').read_text() == 'keep'
    _dispose(app, dialog)


def test_setup_install_result_stays_visible_until_continue(app, tmp_path, monkeypatch):
    dialog = _show(app, setup.SetupWizardV2(diagnose_storage(tmp_path)))
    result = diagnose_storage(tmp_path)
    result.prepare_allowed = False
    result.scan_allowed = result.write_allowed = True
    result.menu_state = 'openmenu_compatible'
    monkeypatch.setattr(setup, '_confirm_dialog', lambda *args: True)
    monkeypatch.setattr(setup, 'install_openmenu_base', lambda *args: result)
    monkeypatch.setattr(setup, 'diagnose_storage', lambda *args: result if dialog._installed else dialog.diagnostic)
    dialog.handle_primary_action()
    assert dialog.isVisible() and dialog.result() != QDialog.DialogCode.Accepted
    assert 'correctamente' in dialog.security_title.text()
    _capture(dialog, 'setup-installed-success')
    dialog.handle_primary_action()
    assert dialog.result() == QDialog.DialogCode.Accepted and dialog.selected_path == tmp_path
    _dispose(app, dialog)


def test_setup_cancelled_and_failed_install_never_accepts(app, tmp_path, monkeypatch):
    dialog = _show(app, setup.SetupWizardV2(diagnose_storage(tmp_path)))
    monkeypatch.setattr(setup, '_confirm_dialog', lambda *args: False)
    calls = []
    monkeypatch.setattr(setup, 'install_openmenu_base', lambda *args: calls.append(args))
    dialog.handle_primary_action()
    assert not calls and dialog.result() != QDialog.DialogCode.Accepted
    monkeypatch.setattr(setup, '_confirm_dialog', lambda *args: True)
    def fail(*args):
        raise OSError('Synthetic failure')
    monkeypatch.setattr(setup, 'install_openmenu_base', fail)
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: None)
    dialog.handle_primary_action()
    assert dialog.isVisible() and dialog.result() != QDialog.DialogCode.Accepted
    _dispose(app, dialog)


def test_setup_backup_blocks_route_close_and_primary(app, tmp_path):
    dialog = _show(app, setup.SetupWizardV2(diagnose_storage(tmp_path)))
    dialog._backup_active = True
    dialog.reject()
    dialog.close()
    dialog.handle_primary_action()
    assert dialog.isVisible() and dialog.result() != QDialog.DialogCode.Accepted
    dialog._backup_active = False
    _dispose(app, dialog)


def retained_cases(tmp_path):
    diagnostic = diagnose_storage(tmp_path)
    yield 'backup', backup_prompt.BackupPromptDialog(diagnostic)
    yield 'upgrade', LegacyMenuUpgradeDialog(False)
    yield 'review', ConfirmApplyDialog(tmp_path, 3, 2, 1, slot_moves=4, product_updates=5)
    yield 'providers', ProviderSettingsDialog({})
    yield 'credentials', ProviderConfigDialog('screenscraper', 'ScreenScraper', {'cover_providers': {'screenscraper': {'ssid': 'user', 'sspassword': 'secret', 'timeout': 30}}})
    yield 'language', LanguageSelectionDialog(available_languages())
    yield 'about', AboutDialog()
    yield 'progress', BulkProgressDialog(3)


def test_every_retained_class_has_real_visual_adapter(app, tmp_path):
    seen = set()
    for name, dialog in retained_cases(tmp_path):
        _show(app, dialog)
        assert dialog.property('v2Retained') and dialog.property('v2LayoutAdapted'), name
        assert type(dialog).__name__ in RETAINED_DIALOGS
        seen.add(type(dialog).__name__)
        _visible_buttons_reachable(dialog)
        for button in dialog.findChildren(QPushButton):
            if button.isVisibleTo(dialog) and button.text():
                assert not button.icon().isNull(), (name, button.text())
        if name == 'review':
            assert (dialog.covers, dialog.additions, dialog.deletions, dialog.slot_moves, dialog.product_updates) == (3, 2, 1, 4, 5)
        if name == 'providers':
            table = dialog.table
            for row in range(table.rowCount()):
                for col in (3, 4, 5, 6):
                    cell = table.cellWidget(row, col)
                    assert cell.width() <= table.columnWidth(col)
                    # Scroll to the real row and column before checking its controls.
                    table.verticalScrollBar().setValue(row)
                    table.horizontalScrollBar().setValue(max(0, table.columnViewportPosition(col)))
                    app.processEvents()
                    point = cell.mapTo(table.viewport(), cell.rect().center())
                    assert table.viewport().rect().contains(point), (row, col, point)
            table.verticalScrollBar().setValue(0)
            table.horizontalScrollBar().setValue(0)
        _capture(dialog, name)
        _dispose(app, dialog)
    assert seen == set(RETAINED_DIALOGS)


def test_message_roles_defaults_and_template_input_are_preserved(app):
    dialog = QMessageBox()
    accept = dialog.addButton('Continue', QMessageBox.ButtonRole.AcceptRole)
    cancel = dialog.addButton('Cancel', QMessageBox.ButtonRole.RejectRole)
    destructive = dialog.addButton('Revert', QMessageBox.ButtonRole.DestructiveRole)
    dialog.setDefaultButton(cancel)
    _show(app, dialog)
    assert dialog.defaultButton() is cancel
    assert accept.property('role') == 'primary' and destructive.property('role') == 'danger'
    assert not accept.icon().isNull()
    _dispose(app, dialog)
    prompt = _show(app, QInputDialog())
    assert prompt.property('v2Retained')
    assert all(not button.icon().isNull() for button in prompt.findChildren(QPushButton))
    _dispose(app, prompt)


def test_spanish_native_message_and_input_buttons(app):
    message = QMessageBox()
    message.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
    _show(app, message)
    assert message.button(QMessageBox.StandardButton.Ok).text() == 'Aceptar'
    assert message.button(QMessageBox.StandardButton.Cancel).text() == 'Cancelar'
    _dispose(app, message)
    prompt = _show(app, QInputDialog())
    assert prompt.okButtonText() == 'Aceptar' and prompt.cancelButtonText() == 'Cancelar'
    _dispose(app, prompt)


def test_backup_cancel_and_close_wait_for_worker_cleanup(app, tmp_path):
    dialog = _show(app, backup_prompt.BackupPromptDialog(diagnose_storage(tmp_path)))
    dialog._backup_active = True
    dialog._set_busy(True, '')
    assert not dialog.cancel_button.isEnabled()
    dialog.reject()
    dialog.close()
    assert dialog.isVisible()
    dialog._backup_stopped()
    assert dialog.cancel_button.isEnabled()
    dialog.reject()
    assert not dialog.isVisible()
    _dispose(app, dialog)


def test_legacy_dialogs_are_not_adapted_without_v2(app):
    app.setProperty('v2Design', False)
    # The filter must be inert for the --legacy-ui fallback in a shared process.
    dialog = LegacyMenuUpgradeDialog(False)
    _show(app, dialog)
    assert not dialog.property('v2Retained')
    _dispose(app, dialog)
    app.setProperty('v2Design', True)


def test_all_original_dialog_exports_have_explicit_v2_disposition():
    import inspect
    from openmenu_gdemu_manager.ui import dialogs
    exported = {name for name, item in inspect.getmembers(dialogs, inspect.isclass) if issubclass(item, QDialog)}
    replaced = {'SetupWizardDialog', 'CandidateDialog', 'CoverPreviewDialog', 'AddGameDialog'}
    assert exported == (set(RETAINED_DIALOGS) - {'ProviderConfigDialog'}) | replaced
