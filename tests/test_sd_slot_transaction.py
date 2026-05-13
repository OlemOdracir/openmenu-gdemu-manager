from pathlib import Path

from openmenu_gdemu_manager.core.models import GameItem
from openmenu_gdemu_manager.services.sd_slot_transaction import (
    SdSlotTransactionService,
    incomplete_slot_transactions,
)


def _slot(root: Path, number: int, marker: str = "disc.gdi") -> Path:
    path = root / f"{number:02d}"
    path.mkdir(parents=True)
    (path / marker).write_text(f"slot {number}", encoding="ascii")
    return path


def _disc_with_product(folder: Path, product: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "disc.gdi").write_text(
        "\n".join(["1", "1 45000 4 2048 track03.iso 0"]),
        encoding="ascii",
    )
    ip = bytearray(0x100)
    ip[:16] = b"SEGA SEGAKATANA "
    ip[0x40:0x50] = product.encode("ascii").ljust(0x10, b" ")
    (folder / "track03.iso").write_bytes(bytes(ip))


def test_build_plan_compacts_sparse_slots():
    service = SdSlotTransactionService(Path("H:/"), "op")
    games = [GameItem(slot=2, name="A"), GameItem(slot=3, name="B"), GameItem(slot=5, name="C"), GameItem(slot=6, name="D")]

    plan = service.build_plan(games)

    assert [entry.to_dict() for entry in plan.moves] == [
        {"action": "move", "name": "C", "old_slot": 5, "new_slot": 4, "product_id": "", "source_path": "", "folder": "H:\\05"},
        {"action": "move", "name": "D", "old_slot": 6, "new_slot": 5, "product_id": "", "source_path": "", "folder": "H:\\06"},
    ]


def test_execute_deletes_to_internal_trash_and_compacts(tmp_path):
    root = tmp_path / "sd"
    slot2 = _slot(root, 2)
    slot3 = _slot(root, 3)
    slot4 = _slot(root, 4)
    games = [
        GameItem(slot=2, name="A", folder=slot2),
        GameItem(slot=3, name="B", folder=slot3, pending_delete=True),
        GameItem(slot=4, name="C", folder=slot4, product_id="SLOT004"),
    ]
    service = SdSlotTransactionService(root, "op-delete")
    plan = service.build_plan(games)

    result = service.execute(plan, games)

    assert (root / "_openmenu_gdemu_manager" / "trash" / "op-delete" / "03" / "disc.gdi").exists()
    assert (root / "03" / "disc.gdi").exists()
    assert not (root / "04").exists()
    assert games[2].slot == 3
    assert games[2].product_id == "SLOT003"
    assert result.moved[0]["old_slot"] == 4
    assert incomplete_slot_transactions(root) == []


def test_execute_adds_from_temporary_copy(tmp_path):
    root = tmp_path / "sd"
    slot2 = _slot(root, 2)
    source = tmp_path / "source_game"
    source.mkdir()
    (source / "disc.cdi").write_text("new game", encoding="ascii")
    games = [
        GameItem(slot=2, name="A", folder=slot2),
        GameItem(slot=3, name="New", source_path=str(source), pending_add=True, is_new=True, product_id="SLOT003"),
    ]
    service = SdSlotTransactionService(root, "op-add")

    result = service.execute(service.build_plan(games), games)

    assert (root / "03" / "disc.cdi").read_text(encoding="ascii") == "new game"
    assert not games[1].pending_add
    assert result.added[0]["new_slot"] == 3


def test_execute_add_uses_real_disc_product_before_rebuilding_menu(tmp_path):
    root = tmp_path / "sd"
    slot2 = _slot(root, 2)
    source = tmp_path / "source_game"
    _disc_with_product(source, "MK51033")
    games = [
        GameItem(slot=2, name="A", folder=slot2),
        GameItem(slot=3, name="Ecco", source_path=str(source), pending_add=True, is_new=True, product_id="SLOT030"),
    ]
    service = SdSlotTransactionService(root, "op-add-product")

    result = service.execute(service.build_plan(games), games)

    assert games[1].product_id == "MK51033"
    assert games[1].artwork_serials == ["SLOT030", "SLOT003", "MK51033"]
    assert result.product_updates == [
        {
            "old_slot": 3,
            "new_slot": 3,
            "name": "Ecco",
            "old_product_id": "SLOT030",
            "new_product_id": "MK51033",
            "artwork_aliases": ["SLOT030", "SLOT003", "MK51033"],
        }
    ]


def test_execute_reorders_without_slot_collisions(tmp_path):
    root = tmp_path / "sd"
    slot2 = _slot(root, 2)
    slot3 = _slot(root, 3)
    games = [
        GameItem(slot=3, name="B", folder=slot3),
        GameItem(slot=2, name="A", folder=slot2),
    ]
    service = SdSlotTransactionService(root, "op-reorder")

    service.execute(service.build_plan(games), games)

    assert (root / "02" / "disc.gdi").read_text(encoding="ascii") == "slot 3"
    assert (root / "03" / "disc.gdi").read_text(encoding="ascii") == "slot 2"
    assert [game.slot for game in games] == [2, 3]


def test_revert_from_state_restores_temp_and_trash(tmp_path):
    root = tmp_path / "sd"
    slot2 = _slot(root, 2)
    slot3 = _slot(root, 3)
    games = [
        GameItem(slot=2, name="A", folder=slot2, pending_delete=True),
        GameItem(slot=3, name="B", folder=slot3),
    ]
    service = SdSlotTransactionService(root, "op-revert")
    plan = service.build_plan(games)
    service.transaction_dir.mkdir(parents=True)
    service._write_json("plan.json", plan.to_dict())
    service.trash_dir.mkdir(parents=True)
    slot2.rename(service.trash_dir / "02")
    service.temp_dir.mkdir(parents=True)
    slot3.rename(service.temp_dir / "03")
    service._write_state("moved_to_temp")

    assert incomplete_slot_transactions(root) == [service.transaction_dir]
    service.revert_from_state()

    assert (root / "02" / "disc.gdi").exists()
    assert (root / "03" / "disc.gdi").exists()
    assert incomplete_slot_transactions(root) == []
