from pathlib import Path

import pytest

from openmenu_gdemu_manager.services.legacy_menu_upgrade import (
    LegacyMenuUpgradeError,
    LegacyMenuUpgradeService,
)
from openmenu_gdemu_manager.services.transaction_log import read_transactions


def _write_openmenu_slot(slot: Path, num_items: int) -> None:
    slot.mkdir(parents=True, exist_ok=True)
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
    (slot / "track05.bin").write_bytes(b"data[OPENMENU]\nopenMenu\nnum_items=%d\n" % num_items)


class _FakeRebuilder:
    def prepare_from_template(self, games, staging_root: Path) -> Path:
        slot = Path(staging_root) / "01"
        _write_openmenu_slot(slot, len(games))
        return slot


class _InvalidRebuilder:
    def prepare_from_template(self, _games, staging_root: Path) -> Path:
        slot = Path(staging_root) / "01"
        slot.mkdir(parents=True)
        (slot / "disc.gdi").write_text("1\n1 0 4 2048 track05.bin 0\n", encoding="ascii")
        (slot / "track05.bin").write_bytes(b"not openmenu")
        return slot


def _legacy_sd(root: Path) -> None:
    (root / "01").mkdir()
    (root / "01" / "old_menu.bin").write_bytes(b"legacy gdmenu")
    (root / "02").mkdir()
    (root / "02" / "Blue Stinger.cdi").write_bytes(b"game")
    (root / "03").mkdir()
    (root / "03" / "Crazy Taxi.cdi").write_bytes(b"game")


def test_legacy_upgrade_replaces_only_slot_01_and_logs(tmp_path):
    _legacy_sd(tmp_path)
    service = LegacyMenuUpgradeService(_FakeRebuilder())

    result = service.upgrade(tmp_path)

    assert result.num_items == 2
    assert (tmp_path / "01" / "disc.gdi").exists()
    assert not (tmp_path / "01" / "old_menu.bin").exists()
    assert (tmp_path / "02" / "Blue Stinger.cdi").exists()
    assert (tmp_path / "03" / "Crazy Taxi.cdi").exists()
    events = read_transactions(tmp_path)
    assert any(event["operation"] == "legacy_menu_upgrade" and event["result"] == "success" for event in events)


def test_legacy_upgrade_keeps_old_menu_when_new_slot_is_invalid(tmp_path):
    _legacy_sd(tmp_path)
    service = LegacyMenuUpgradeService(_InvalidRebuilder())

    with pytest.raises(LegacyMenuUpgradeError):
        service.upgrade(tmp_path)

    assert (tmp_path / "01" / "old_menu.bin").exists()
    assert not (tmp_path / "01.new").exists()
    events = read_transactions(tmp_path)
    assert any(event["operation"] == "legacy_menu_upgrade" and event["result"] == "failed" for event in events)


def test_legacy_upgrade_rejects_non_migratable_path(tmp_path):
    (tmp_path / "notes.txt").write_text("not gdemu", encoding="utf-8")
    service = LegacyMenuUpgradeService(_FakeRebuilder())

    with pytest.raises(LegacyMenuUpgradeError, match="migrable"):
        service.upgrade(tmp_path)
