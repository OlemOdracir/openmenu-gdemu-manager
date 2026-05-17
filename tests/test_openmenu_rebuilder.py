from pathlib import Path

import pytest
import subprocess

from openmenu_gdemu_manager.services.openmenu_rebuilder import (
    OpenMenuRebuildConfig,
    OpenMenuRebuildError,
    OpenMenuRebuilder,
    _run_buildgdi,
    _artwork_serial_aliases,
    validate_rebuilt_slot,
)
from openmenu_gdemu_manager.core.models import GameItem


def _write_valid_slot(slot: Path, num_items: int = 2) -> None:
    slot.mkdir(parents=True)
    (slot / "disc.gdi").write_text(
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
    (slot / "track01.iso").write_bytes(b"low")
    (slot / "track02.raw").write_bytes(b"raw")
    (slot / "track03.bin").write_bytes(b"boot")
    (slot / "track04.raw").write_bytes(b"raw")
    (slot / "track05.bin").write_bytes(b"data[OPENMENU]\nnum_items=%d\n" % num_items)


def test_validate_rebuilt_slot_accepts_declared_tracks_and_menu(tmp_path):
    slot = tmp_path / "01"
    _write_valid_slot(slot, num_items=2)

    validate_rebuilt_slot(slot, expected_items=2)


def test_validate_rebuilt_slot_rejects_missing_declared_track(tmp_path):
    slot = tmp_path / "01"
    _write_valid_slot(slot)
    (slot / "track05.bin").unlink()

    with pytest.raises(OpenMenuRebuildError, match="Faltan tracks"):
        validate_rebuilt_slot(slot)


def test_rebuilder_reports_missing_buildgdi_before_touching_staging(tmp_path):
    menu_gdi = tmp_path / "menu_gdi"
    _write_valid_slot(menu_gdi)
    config = OpenMenuRebuildConfig(
        buildgdi_path=tmp_path / "missing-buildgdi.exe",
        menu_gdi_dir=menu_gdi,
        menu_data_dir=None,
        backup_dir=tmp_path / "backups",
    )
    rebuilder = OpenMenuRebuilder(config)

    with pytest.raises(OpenMenuRebuildError, match="buildgdi"):
        rebuilder.prepare_staging(tmp_path / "sd", [], tmp_path / "staging")


def test_rebuilder_rejects_unvalidated_buildgdi_hash(tmp_path):
    buildgdi = tmp_path / "buildgdi.exe"
    buildgdi.write_bytes(b"unexpected executable")
    menu_gdi = tmp_path / "menu_gdi"
    _write_valid_slot(menu_gdi)
    config = OpenMenuRebuildConfig(
        buildgdi_path=buildgdi,
        menu_gdi_dir=menu_gdi,
        menu_data_dir=None,
        backup_dir=tmp_path / "backups",
        expected_buildgdi_sha256="00",
    )
    rebuilder = OpenMenuRebuilder(config)

    with pytest.raises(OpenMenuRebuildError, match="SHA256"):
        rebuilder.prepare_staging(tmp_path / "sd", [], tmp_path / "staging")


def test_rebuilder_preserves_visible_cover_when_dat_entry_is_missing(monkeypatch, tmp_path):
    current_cover = tmp_path / "current.png"
    selected_cover = tmp_path / "selected.png"
    current_cover.write_bytes(b"current")
    selected_cover.write_bytes(b"selected")
    captured: dict[str, Path] = {}

    monkeypatch.setattr(
        "openmenu_gdemu_manager.services.openmenu_rebuilder._existing_box_serials",
        lambda data_dir: {"EXISTS"},
    )

    def fake_update_artwork_dats(data_dir: Path, updates: dict[str, Path]) -> int:
        captured.update(updates)
        return len(updates)

    monkeypatch.setattr(
        "openmenu_gdemu_manager.services.openmenu_rebuilder.update_artwork_dats",
        fake_update_artwork_dats,
    )
    rebuilder = OpenMenuRebuilder(
        OpenMenuRebuildConfig(
            buildgdi_path=tmp_path / "buildgdi.exe",
            menu_gdi_dir=tmp_path / "menu_gdi",
        )
    )

    changed = rebuilder._update_artwork(
        tmp_path / "data",
        [
            GameItem(slot=100, name="METAL SLUG", product_id="SLOT015", current_cover=current_cover),
            GameItem(slot=101, name="METAL SLUG 2", product_id="EXISTS", current_cover=current_cover),
            GameItem(slot=102, name="METAL SLUG 6", product_id="SLOT106", selected_image=str(selected_cover)),
        ],
    )

    assert changed == 4
    assert captured == {
        "SLOT015": current_cover,
        "SLOT100": current_cover,
        "SLOT106": selected_cover,
        "SLOT102": selected_cover,
    }


def test_artwork_serial_aliases_include_current_slot_and_disc_product_for_synthetic_ids(tmp_path):
    slot = tmp_path / "102"
    slot.mkdir()
    (slot / "disc.gdi").write_text(
        "\n".join(["2", "1 0 4 2048 track01.iso 0", "2 45000 4 2048 track03.iso 0"]),
        encoding="ascii",
    )
    ip = bytearray(0x60)
    ip[:16] = b"SEGA SEGAKATANA "
    ip[0x40:0x50] = b"T0000M    V1.000"
    (slot / "track03.iso").write_bytes(bytes(ip))
    game = GameItem(slot=102, name="METAL SLUG 6", product_id="SLOT106", folder=slot)

    assert _artwork_serial_aliases(game) == ["SLOT106", "SLOT102", "T0000M"]


def test_replace_slot_01_restores_previous_slot_if_final_validation_fails(monkeypatch, tmp_path):
    root = tmp_path / "sd"
    current = root / "01"
    staging = tmp_path / "staging" / "01"
    _write_valid_slot(current, num_items=3)
    _write_valid_slot(staging, num_items=3)
    rebuilder = OpenMenuRebuilder(
        OpenMenuRebuildConfig(
            buildgdi_path=tmp_path / "buildgdi.exe",
            menu_gdi_dir=tmp_path / "menu_gdi",
            backup_dir=tmp_path / "backups",
        )
    )
    call_counter = {"count": 0}
    original_validate = validate_rebuilt_slot

    def fail_after_swap(slot_path: Path, expected_items=None):
        call_counter["count"] += 1
        if call_counter["count"] == 3:
            raise OpenMenuRebuildError("forced final validation failure")
        return original_validate(slot_path, expected_items=expected_items)

    monkeypatch.setattr("openmenu_gdemu_manager.services.openmenu_rebuilder.validate_rebuilt_slot", fail_after_swap)

    with pytest.raises(OpenMenuRebuildError, match="se restauro el backup"):
        rebuilder.replace_slot_01(root, staging)

    assert (root / "01" / "track05.bin").exists()
    assert any(path.name.startswith("01-before-rebuild-") for path in (tmp_path / "backups").iterdir())


def test_run_buildgdi_returns_timeout_code(monkeypatch):
    def _timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd=["buildgdi"], timeout=1, stderr="hung")

    monkeypatch.setattr("subprocess.run", _timeout)

    result = _run_buildgdi(["buildgdi"], timeout_seconds=1)

    assert result.returncode == 124
    assert "tiempo limite" in (result.stderr or "")
