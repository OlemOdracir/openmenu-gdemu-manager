import json

import pytest

from openmenu_gdemu_manager.services.backup_service import BackupError, backup_sd_contents, suggested_backup_dir


def test_backup_sd_contents_copies_files_and_manifest(tmp_path):
    source = tmp_path / "sd"
    source.mkdir()
    (source / "01").mkdir()
    (source / "01" / "track05.iso").write_bytes(b"openmenu")
    destination = tmp_path / "backup"

    result = backup_sd_contents(source, destination)

    assert result == destination.resolve()
    assert (destination / "01" / "track05.iso").read_bytes() == b"openmenu"
    manifest = json.loads((destination / "backup_manifest.json").read_text(encoding="utf-8"))
    assert manifest["file_count"] == 1
    assert manifest["source"] == str(source.resolve())


def test_backup_rejects_destination_inside_source(tmp_path):
    source = tmp_path / "sd"
    source.mkdir()
    destination = source / "backup"

    with pytest.raises(BackupError):
        backup_sd_contents(source, destination)


def test_backup_allows_non_empty_destination_after_ui_warning(tmp_path):
    source = tmp_path / "sd"
    source.mkdir()
    (source / "01").mkdir()
    (source / "01" / "track05.iso").write_bytes(b"new")
    destination = tmp_path / "backup"
    (destination / "01").mkdir(parents=True)
    (destination / "01" / "track05.iso").write_bytes(b"old")

    backup_sd_contents(source, destination)

    assert (destination / "01" / "track05.iso").read_bytes() == b"new"


def test_suggested_backup_dir_uses_base_dir(tmp_path):
    suggestion = suggested_backup_dir(tmp_path / "H", tmp_path / "Backups")

    assert suggestion.parent == tmp_path / "Backups"
    assert suggestion.name.startswith("SD_")
