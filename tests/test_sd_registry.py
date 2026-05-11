import json

from openmenu_gdemu_manager.services.sd_registry import (
    backup_registry_path,
    last_backup_path,
    read_backup_registry,
    registered_backup_exists,
    write_backup_registry,
)


def test_write_backup_registry_records_existing_backup(tmp_path):
    sd_root = tmp_path / "sd"
    backup = tmp_path / "backup"
    sd_root.mkdir()
    backup.mkdir()

    written = write_backup_registry(sd_root, backup, app_version="test-version")

    assert written == backup_registry_path(sd_root)
    data = read_backup_registry(sd_root)
    assert data["schema_version"] == 1
    assert data["last_backup"]["path"] == str(backup.resolve())
    assert data["last_backup"]["app_version"] == "test-version"
    assert data["last_backup"]["source_root"] == str(sd_root.resolve())
    assert last_backup_path(sd_root) == backup.resolve()
    assert registered_backup_exists(sd_root) is True


def test_registered_backup_exists_rejects_missing_backup(tmp_path):
    sd_root = tmp_path / "sd"
    sd_root.mkdir()
    missing_backup = tmp_path / "missing"
    write_backup_registry(sd_root, missing_backup, app_version="test-version")

    assert last_backup_path(sd_root) == missing_backup.resolve()
    assert registered_backup_exists(sd_root) is False


def test_read_backup_registry_tolerates_corrupt_json(tmp_path):
    sd_root = tmp_path / "sd"
    sd_root.mkdir()
    path = backup_registry_path(sd_root)
    path.parent.mkdir()
    path.write_text("{not json", encoding="utf-8")

    assert read_backup_registry(sd_root) is None
    assert last_backup_path(sd_root) is None
    assert registered_backup_exists(sd_root) is False


def test_last_backup_path_ignores_missing_path_field(tmp_path):
    sd_root = tmp_path / "sd"
    sd_root.mkdir()
    path = backup_registry_path(sd_root)
    path.parent.mkdir()
    path.write_text(json.dumps({"schema_version": 1, "last_backup": {}}), encoding="utf-8")

    assert last_backup_path(sd_root) is None
