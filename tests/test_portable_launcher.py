import importlib.util
import sys
from pathlib import Path


def _load_launcher():
    root = Path(__file__).resolve().parents[1]
    launcher_path = root / "scripts" / "portable_launcher.py"
    spec = importlib.util.spec_from_file_location("portable_launcher", launcher_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_portable_launcher_sets_data_paths_next_to_frozen_exe(tmp_path, monkeypatch):
    module = _load_launcher()
    exe_path = tmp_path / "OpenMenuGDEMUManager.exe"

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe_path))
    monkeypatch.delenv("OPENMENU_GDEMU_MANAGER_HOME", raising=False)
    monkeypatch.delenv("OPENMENU_GDEMU_MANAGER_DOCUMENTS", raising=False)

    module.configure_portable_environment()

    assert sys.executable == str(exe_path)
    assert module.os.environ["OPENMENU_GDEMU_MANAGER_HOME"] == str(tmp_path / "data")
    assert module.os.environ["OPENMENU_GDEMU_MANAGER_DOCUMENTS"] == str(
        tmp_path / "data" / "Documents"
    )


def test_portable_launcher_does_not_override_existing_env(tmp_path, monkeypatch):
    module = _load_launcher()

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "OpenMenuGDEMUManager.exe"))
    monkeypatch.setenv("OPENMENU_GDEMU_MANAGER_HOME", "custom-home")
    monkeypatch.setenv("OPENMENU_GDEMU_MANAGER_DOCUMENTS", "custom-docs")

    module.configure_portable_environment()

    assert module.os.environ["OPENMENU_GDEMU_MANAGER_HOME"] == "custom-home"
    assert module.os.environ["OPENMENU_GDEMU_MANAGER_DOCUMENTS"] == "custom-docs"
