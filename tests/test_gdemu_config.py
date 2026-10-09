"""Configuration is optional and read-only, independent of disc/storage integrity."""
from pathlib import Path
import pytest
from openmenu_gdemu_manager.dreamcast.gdemu_config import inspect_gdemu_config, MAX_CONFIG_BYTES
from openmenu_gdemu_manager.dreamcast.storage_diagnostics import diagnose_storage


def write(root, text):
    path = root / "GDEMU.ini"
    path.write_text(text, encoding="utf-8")
    return path


@pytest.mark.parametrize("key,values", [
    ("open_time", (150, 5000)), ("detect_time", (150, 5000)),
    ("image_tests", (0, 1)), ("high_speed", (0, 1)),
    ("reset_goto", (0, 9999)), ("read_limit", (-1, 0, 600, 1250)),
])
def test_documented_boundaries_and_special_values(tmp_path, key, values):
    for value in values:
        write(tmp_path, f"{key} = {value}\n")
        result = inspect_gdemu_config(tmp_path)
        assert result.status == "valid"
        assert result.settings[0].valid


@pytest.mark.parametrize("key,value", [
    ("open_time", "149"), ("detect_time", "5001"), ("image_tests", "2"),
    ("high_speed", "-1"), ("reset_goto", "10000"), ("read_limit", "599"),
    ("read_limit", "1251"), ("read_limit", "-2"), ("open_time", "1.5"),
    ("image_tests", "true"), ("open_time", ""), ("open_time", "9" * 5000),
])
def test_bad_values_are_findings_without_mutating_bytes(tmp_path, key, value):
    path = write(tmp_path, f"{key} = {value}\n")
    before = path.read_bytes()
    result = inspect_gdemu_config(tmp_path)
    assert result.status == "invalid"
    assert result.findings[0].code == "value"
    assert path.read_bytes() == before


def test_comments_bom_and_blank_optional_configuration(tmp_path):
    path = write(tmp_path, "\ufeff; comment\n# comment\nopen_time = 150 ; trailing comment\nread_limit=-1\n")
    assert inspect_gdemu_config(tmp_path).status == "valid"
    path.write_bytes(b"")
    assert inspect_gdemu_config(tmp_path).status == "valid"
    path.unlink()
    assert inspect_gdemu_config(tmp_path).status == "missing"


def test_unknown_sections_and_keys_are_unverified_not_corruption(tmp_path):
    write(tmp_path, "future_option=5\n[GDEMU]\nopen_time=149\n")
    result = inspect_gdemu_config(tmp_path)
    assert result.status == "review" and not result.settings
    assert [f.code for f in result.findings] == ["unknown_key", "section", "unknown_key"]


def test_duplicate_and_unrecognized_syntax_are_distinct(tmp_path):
    write(tmp_path, "open_time=150\nOPEN_TIME=250\nnot a setting\n")
    result = inspect_gdemu_config(tmp_path)
    assert result.status == "invalid"
    assert [f.code for f in result.findings] == ["duplicate", "syntax"]
    assert [s.value for s in result.settings] == ["150", "250"]


def test_directory_oversize_encoding_and_io_failures_are_nonfatal(tmp_path, monkeypatch):
    path = tmp_path / "GDEMU.ini"
    path.mkdir()
    assert inspect_gdemu_config(tmp_path).status == "unreadable"
    path.rmdir()
    path.write_bytes(b"x" * (MAX_CONFIG_BYTES + 1))
    assert inspect_gdemu_config(tmp_path).findings[0].code == "too_large"
    path.write_bytes("open_time=150".encode("utf-16"))
    assert inspect_gdemu_config(tmp_path).status == "review"
    monkeypatch.setattr(Path, "open", lambda *args, **kw: (_ for _ in ()).throw(PermissionError()))
    assert inspect_gdemu_config(tmp_path).findings[0].code == "read_error"


def test_symlink_escape_is_not_read(tmp_path):
    folder = tmp_path / "sd"
    folder.mkdir()
    outside = tmp_path / "external.ini"
    outside.write_text("open_time=150")
    try:
        (folder / "GDEMU.ini").symlink_to(outside)
    except OSError:
        pytest.skip("Symlink creation is unavailable")
    result = inspect_gdemu_config(folder)
    assert result.status == "unreadable" and not result.settings


def test_missing_and_bad_config_do_not_change_permissions_or_image_classification(tmp_path):
    slot = tmp_path / "01"
    slot.mkdir()
    (slot / "track05.iso").write_bytes(b"[OPENMENU] openMenu NEODC_1")
    missing = diagnose_storage(tmp_path)
    config = write(tmp_path, "open_time=1\nimage_tests=0\n")
    before = config.read_bytes()
    invalid = diagnose_storage(tmp_path)
    assert missing.configuration.status == "missing" and invalid.configuration.status == "invalid"
    assert invalid.write_allowed == missing.write_allowed == True
    assert invalid.scan_allowed == missing.scan_allowed == True
    assert invalid.storage_health == missing.storage_health
    assert invalid.menu_state == missing.menu_state
    assert config.read_bytes() == before


def test_unrelated_destination_does_not_inspect_configuration(tmp_path, monkeypatch):
    (tmp_path / "private.txt").write_text("keep")
    import openmenu_gdemu_manager.dreamcast.storage_diagnostics as storage
    monkeypatch.setattr(storage, "inspect_gdemu_config", lambda *a: pytest.fail("Unrelated configuration read"))
    assert diagnose_storage(tmp_path).configuration is None
