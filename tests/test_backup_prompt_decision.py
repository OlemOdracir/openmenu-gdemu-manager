from types import SimpleNamespace

from openmenu_gdemu_manager.dreamcast.storage_diagnostics import diagnose_storage
from openmenu_gdemu_manager.services.backup_service import set_backup_decision
from openmenu_gdemu_manager.services.sd_registry import registered_backup_exists, write_backup_registry
import openmenu_gdemu_manager.ui.dialogs.backup_prompt as backup_prompt
from openmenu_gdemu_manager.ui.dialogs.backup_prompt import BackupPromptDialog
from openmenu_gdemu_manager.ui.main_window import MainWindow


def _window_for_backup_decision(settings=None):
    window = MainWindow.__new__(MainWindow)
    window.settings = settings or {"ui": {"backup_decisions": {}}}
    window.backup_suggested_roots = set()
    return window


def _diagnostic_for_openmenu_sd(root, *, include_game_slot=True):
    slot1 = root / "01"
    slot1.mkdir()
    (slot1 / "track05.iso").write_bytes(b"prefix [OPENMENU] openMenu NEODC_1 suffix")
    if include_game_slot:
        slot2 = root / "02"
        slot2.mkdir()
        (slot2 / "disc.gdi").write_text("game", encoding="ascii")
    return diagnose_storage(root)


def test_should_not_suggest_backup_when_sd_registry_points_to_existing_backup(tmp_path):
    sd_root = tmp_path / "sd"
    backup = tmp_path / "backup"
    sd_root.mkdir()
    backup.mkdir()
    diagnostic = _diagnostic_for_openmenu_sd(sd_root)
    write_backup_registry(sd_root, backup)

    assert _window_for_backup_decision()._should_suggest_backup(diagnostic) is False


def test_should_suggest_backup_when_sd_registry_points_to_missing_backup(tmp_path):
    sd_root = tmp_path / "sd"
    sd_root.mkdir()
    diagnostic = _diagnostic_for_openmenu_sd(sd_root)
    write_backup_registry(sd_root, tmp_path / "missing")

    assert _window_for_backup_decision()._should_suggest_backup(diagnostic) is True


def test_should_suggest_backup_when_only_local_backed_up_decision_exists(tmp_path):
    sd_root = tmp_path / "sd"
    backup = tmp_path / "backup"
    sd_root.mkdir()
    backup.mkdir()
    diagnostic = _diagnostic_for_openmenu_sd(sd_root)
    settings = set_backup_decision({"ui": {"backup_decisions": {}}}, diagnostic, "backed_up", backup)

    assert _window_for_backup_decision(settings)._should_suggest_backup(diagnostic) is True


def test_should_not_suggest_backup_when_local_skip_decision_exists(tmp_path):
    sd_root = tmp_path / "sd"
    sd_root.mkdir()
    diagnostic = _diagnostic_for_openmenu_sd(sd_root)
    settings = set_backup_decision({"ui": {"backup_decisions": {}}}, diagnostic, "skipped")

    assert _window_for_backup_decision(settings)._should_suggest_backup(diagnostic) is False


def test_should_not_suggest_backup_when_openmenu_base_has_no_games(tmp_path):
    sd_root = tmp_path / "sd"
    sd_root.mkdir()
    diagnostic = _diagnostic_for_openmenu_sd(sd_root, include_game_slot=False)

    assert _window_for_backup_decision()._should_suggest_backup(diagnostic) is False


def test_backup_prompt_finished_writes_local_decision_and_sd_registry(tmp_path, monkeypatch):
    sd_root = tmp_path / "sd"
    backup = tmp_path / "backup"
    sd_root.mkdir()
    backup.mkdir()
    diagnostic = _diagnostic_for_openmenu_sd(sd_root)
    saved = {}
    fake_dialog = SimpleNamespace(
        diagnostic=diagnostic,
        settings={"ui": {"backup_decisions": {}}},
        _set_busy=lambda *_args: None,
        accept=lambda: None,
    )
    monkeypatch.setattr(backup_prompt, "save_settings", lambda settings: saved.update(settings))
    monkeypatch.setattr(backup_prompt.QMessageBox, "information", lambda *_args, **_kwargs: None)

    BackupPromptDialog.backup_finished(fake_dialog, str(backup))

    assert registered_backup_exists(sd_root) is True
    assert saved["ui"]["backup_decisions"]
