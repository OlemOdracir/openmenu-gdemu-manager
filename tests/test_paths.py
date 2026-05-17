import importlib
import sys


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


def test_bundled_buildgdi_uses_pyinstaller_internal_dir(tmp_path, monkeypatch):
    import openmenu_gdemu_manager.config.paths as paths

    internal = tmp_path / "_internal"
    buildgdi = internal / "third_party" / "buildgdi" / "buildgdi.exe"
    buildgdi.parent.mkdir(parents=True)
    buildgdi.write_bytes(b"buildgdi")

    with monkeypatch.context() as scoped:
        scoped.setattr(sys, "frozen", True, raising=False)
        scoped.setattr(sys, "_MEIPASS", str(internal), raising=False)
        scoped.setattr(sys, "executable", str(tmp_path / "OpenMenuGDEMUManager.exe"))

        reloaded = importlib.reload(paths)

        assert reloaded.BUNDLED_BUILDGDI_PATH == buildgdi.resolve()

    importlib.reload(paths)


def test_bundled_openmenu_uses_pyinstaller_internal_dir(tmp_path, monkeypatch):
    import openmenu_gdemu_manager.config.paths as paths

    internal = tmp_path / "_internal"
    openmenu = internal / "third_party" / "openmenu"
    (openmenu / "menu_gdi").mkdir(parents=True)
    (openmenu / "menu_data").mkdir()

    with monkeypatch.context() as scoped:
        scoped.setattr(sys, "frozen", True, raising=False)
        scoped.setattr(sys, "_MEIPASS", str(internal), raising=False)
        scoped.setattr(sys, "executable", str(tmp_path / "OpenMenuGDEMUManager.exe"))

        reloaded = importlib.reload(paths)

        assert reloaded.BUNDLED_OPENMENU_TOOLS_DIR == openmenu.resolve()

    importlib.reload(paths)
