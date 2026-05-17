from pathlib import Path

import openmenu_gdemu_manager.dreamcast.storage_diagnostics as storage_diagnostics
from openmenu_gdemu_manager.dreamcast.storage_diagnostics import (
    ROUTE_EMPTY_SAFE,
    MENU_OPENMENU_COMPATIBLE,
    diagnose_storage,
    recommended_initial_storage_path,
)
from openmenu_gdemu_manager.services.setup_service import OpenMenuSetupError, install_openmenu_base


def test_diagnose_storage_empty_path_can_be_prepared(tmp_path):
    diagnostic = diagnose_storage(tmp_path)

    assert diagnostic.route_class == ROUTE_EMPTY_SAFE
    assert diagnostic.prepare_allowed is True
    assert diagnostic.scan_allowed is False
    assert diagnostic.write_allowed is False
    assert diagnostic.summary.other_entries == []


def test_diagnose_storage_ignores_os_metadata_for_empty_path(tmp_path):
    (tmp_path / "WPSettings.dat").write_text("", encoding="utf-8")
    (tmp_path / "GDEMU.ini").write_text("", encoding="utf-8")
    (tmp_path / "System Volume Information").mkdir()
    (tmp_path / "_openmenu_gdemu_manager").mkdir()

    diagnostic = diagnose_storage(tmp_path)

    assert diagnostic.route_class == ROUTE_EMPTY_SAFE
    assert diagnostic.prepare_allowed is True
    assert diagnostic.summary.other_entries == []
    assert sorted(name.lower() for name in diagnostic.summary.ignored_entries) == [
        "_openmenu_gdemu_manager",
        "gdemu.ini",
        "system volume information",
        "wpsettings.dat",
    ]


def test_diagnose_storage_real_non_gdemu_content_is_not_prepare_allowed(tmp_path):
    (tmp_path / "notes.txt").write_text("not gdemu", encoding="utf-8")

    diagnostic = diagnose_storage(tmp_path)

    assert diagnostic.prepare_allowed is False
    assert diagnostic.scan_allowed is False
    assert diagnostic.write_allowed is False
    assert diagnostic.summary.other_entries == ["notes.txt"]


def test_diagnose_storage_does_not_treat_games_folder_name_as_personal_data(tmp_path):
    (tmp_path / "Juegos").mkdir()

    diagnostic = diagnose_storage(tmp_path)

    assert diagnostic.route_class != "dangerous_path"
    assert "datos personales" not in diagnostic.reason
    assert diagnostic.write_allowed is False


def test_diagnose_storage_accepts_local_openmenu_backup(tmp_path):
    slot1 = tmp_path / "01"
    slot1.mkdir()
    (slot1 / "track05.iso").write_bytes(b"prefix [OPENMENU] openMenu NEODC_1 suffix")

    diagnostic = diagnose_storage(tmp_path)

    assert diagnostic.scan_allowed is True
    assert diagnostic.write_allowed is True
    assert diagnostic.menu_state == MENU_OPENMENU_COMPATIBLE


def test_diagnose_storage_ignores_sd_registry_with_gdemu_structure(tmp_path):
    slot1 = tmp_path / "01"
    slot1.mkdir()
    (slot1 / "track05.iso").write_bytes(b"prefix [OPENMENU] openMenu NEODC_1 suffix")
    (tmp_path / "_openmenu_gdemu_manager").mkdir()

    diagnostic = diagnose_storage(tmp_path)

    assert diagnostic.scan_allowed is True
    assert diagnostic.write_allowed is True
    assert "_openmenu_gdemu_manager" in diagnostic.summary.ignored_entries
    assert "_openmenu_gdemu_manager" not in diagnostic.summary.other_entries


def test_diagnose_storage_detects_rebuilt_openmenu_track05_bin(tmp_path):
    slot1 = tmp_path / "01"
    slot1.mkdir()
    (slot1 / "disc.gdi").write_text(
        "\n".join(
            [
                "5",
                "1 0 4 2048 track01.iso 0",
                "2 450 0 2352 track02.raw 0",
                "3 45000 4 2048 track03.bin 0",
                "4 487657 0 2352 track04.raw 0",
                "5 487808 4 2048 track05.bin 0",
            ]
        ),
        encoding="ascii",
    )
    (slot1 / "track03.bin").write_bytes(b"boot")
    (slot1 / "track05.bin").write_bytes(b"prefix [OPENMENU] openMenu NEODC_1 suffix")

    diagnostic = diagnose_storage(tmp_path)

    assert diagnostic.scan_allowed is True
    assert diagnostic.write_allowed is True
    assert diagnostic.menu_state == MENU_OPENMENU_COMPATIBLE


def test_install_openmenu_base_copies_slot_01_and_rediagnoses(tmp_path):
    template = tmp_path / "template"
    source_slot = template / "01"
    source_slot.mkdir(parents=True)
    (source_slot / "track05.iso").write_bytes(b"prefix [OPENMENU] openMenu NEODC_1 suffix")

    target = tmp_path / "target"
    target.mkdir()
    diagnostic = install_openmenu_base(target, {"openmenu_setup": {"template_dir": str(template)}})

    assert (target / "01" / "track05.iso").exists()
    assert diagnostic.scan_allowed is True
    assert diagnostic.write_allowed is True
    assert diagnostic.menu_state == MENU_OPENMENU_COMPATIBLE


def test_install_openmenu_base_rejects_path_that_is_no_longer_empty(tmp_path):
    template = tmp_path / "template"
    (template / "01").mkdir(parents=True)
    target = tmp_path / "target"
    target.mkdir()
    (target / "notes.txt").write_text("dirty", encoding="utf-8")

    try:
        install_openmenu_base(target, {"openmenu_setup": {"template_dir": str(template)}})
    except OpenMenuSetupError as exc:
        assert "no esta vacia" in str(exc)
    else:
        raise AssertionError("Expected OpenMenuSetupError")


def test_recommended_initial_storage_path_prefers_compatible_removable(monkeypatch, tmp_path):
    fallback = tmp_path / "portable"
    empty = tmp_path / "empty"
    compatible = tmp_path / "sd"
    fallback.mkdir()
    empty.mkdir()
    slot1 = compatible / "01"
    slot1.mkdir(parents=True)
    (slot1 / "track05.iso").write_bytes(b"prefix [OPENMENU] openMenu NEODC_1 suffix")
    monkeypatch.setattr(storage_diagnostics, "_logical_drive_roots", lambda: [empty, compatible])
    monkeypatch.setattr(storage_diagnostics, "_drive_type", lambda _root: "removable")
    monkeypatch.setattr(storage_diagnostics, "_filesystem", lambda _root: "FAT32")

    assert recommended_initial_storage_path(fallback) == compatible


def test_recommended_initial_storage_path_uses_empty_removable_before_fallback(monkeypatch, tmp_path):
    fallback = tmp_path / "portable"
    empty = tmp_path / "empty"
    fallback.mkdir()
    empty.mkdir()
    monkeypatch.setattr(storage_diagnostics, "_logical_drive_roots", lambda: [empty])
    monkeypatch.setattr(storage_diagnostics, "_drive_type", lambda _root: "removable")
    monkeypatch.setattr(storage_diagnostics, "_filesystem", lambda _root: "FAT32")

    assert recommended_initial_storage_path(fallback) == empty


def test_recommended_initial_storage_path_uses_fallback_without_removable(monkeypatch, tmp_path):
    fallback = tmp_path / "portable"
    fallback.mkdir()
    monkeypatch.setattr(storage_diagnostics, "_logical_drive_roots", lambda: [])

    assert recommended_initial_storage_path(fallback) == fallback


def test_logical_drive_roots_reads_all_windows_drives(monkeypatch):
    class _Kernel32:
        @staticmethod
        def GetLogicalDriveStringsW(_size, buffer):
            raw = "C:\\\x00E:\\\x00\x00"
            for index, char in enumerate(raw):
                buffer[index] = char
            return len(raw)

    class _Windll:
        kernel32 = _Kernel32()

    monkeypatch.setattr(storage_diagnostics.ctypes, "windll", _Windll(), raising=False)

    assert storage_diagnostics._logical_drive_roots() == [Path("C:\\"), Path("E:\\")]
