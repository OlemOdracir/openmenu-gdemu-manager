import importlib


def test_runtime_paths_default_to_current_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)

    import openmenu_gdemu_manager.config.paths as paths

    reloaded = importlib.reload(paths)

    assert reloaded.BASE_DIR == tmp_path.resolve()
    assert reloaded.STATE_PATH == tmp_path / "_cover_manager_state.json"
    assert reloaded.LOG_PATH == tmp_path / "openmenu_gdemu_manager.log"


def test_runtime_paths_use_localappdata_on_windows(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "LocalAppData"))
    monkeypatch.delenv("OPENMENU_GDEMU_MANAGER_HOME", raising=False)

    import openmenu_gdemu_manager.config.paths as paths

    reloaded = importlib.reload(paths)

    assert reloaded.BASE_DIR == (tmp_path / "LocalAppData" / "OpenMenu GDEMU Manager").resolve()
