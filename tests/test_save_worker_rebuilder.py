from pathlib import Path
from types import SimpleNamespace

from openmenu_gdemu_manager.core.models import GameItem
from openmenu_gdemu_manager.services.transaction_log import read_transactions
from openmenu_gdemu_manager.ui import workers


class FakeRebuilder:
    called_with: tuple[Path, list[GameItem]] | None = None

    def rebuild_and_replace(self, root_path: Path, games: list[GameItem]):
        FakeRebuilder.called_with = (Path(root_path), list(games))
        return SimpleNamespace(num_items=len(games), backup_slot=Path("backup/01"))


def test_save_changes_uses_rebuilder_instead_of_track05_capacity(monkeypatch, tmp_path):
    root = tmp_path / "sd"
    slot1 = root / "01"
    slot2 = root / "02"
    slot1.mkdir(parents=True)
    slot2.mkdir()
    (slot1 / "track05.iso").write_bytes(b"prefix[OPENMENU]\nold=1\n" + (b"\x00" * 64))
    game = GameItem(slot=2, name="A" * 500, folder=slot2, product_id="LONGPRODUCT", region="U")

    FakeRebuilder.called_with = None
    monkeypatch.setattr(workers, "OpenMenuRebuilder", lambda: FakeRebuilder())
    monkeypatch.setattr(workers, "write_openmenu_ini", lambda games: "")
    monkeypatch.setattr(workers, "write_name_txt", lambda folder, title: None)
    monkeypatch.setattr(workers, "patch_game_state", lambda state, root_path, game: None)
    monkeypatch.setattr(workers, "flush_state", lambda path, state: None)

    finished: list[str] = []
    errors: list[str] = []
    worker = workers.SaveChangesWorker(root, [game], {}, write_allowed=True)
    worker.finished.connect(finished.append)
    worker.error.connect(errors.append)

    worker.run()

    assert errors == []
    assert finished
    assert FakeRebuilder.called_with is not None
    assert FakeRebuilder.called_with[0] == root
    assert [item.slot for item in FakeRebuilder.called_with[1]] == [2]
    transactions = read_transactions(root)
    assert [entry["result"] for entry in transactions] == ["pending", "success"]


def test_save_changes_logs_rename_transaction(monkeypatch, tmp_path):
    root = tmp_path / "sd"
    slot1 = root / "01"
    slot2 = root / "02"
    slot1.mkdir(parents=True)
    slot2.mkdir()
    (slot1 / "track05.iso").write_bytes(
        b"prefix[OPENMENU]\n"
        b"num_items=1\n"
        b"02.name=Old Name\n"
        b"02.product_id=TST-001\n"
        b"\x00" * 64
    )
    game = GameItem(
        slot=2,
        name="New Name",
        folder=slot2,
        product_id="TST-001",
        region="U",
        save_status="pendiente_guardar",
    )

    FakeRebuilder.called_with = None
    monkeypatch.setattr(workers, "OpenMenuRebuilder", lambda: FakeRebuilder())
    monkeypatch.setattr(workers, "write_openmenu_ini", lambda games: "")
    monkeypatch.setattr(workers, "write_name_txt", lambda folder, title: None)
    monkeypatch.setattr(workers, "patch_game_state", lambda state, root_path, game: None)
    monkeypatch.setattr(workers, "flush_state", lambda path, state: None)

    finished: list[str] = []
    errors: list[str] = []
    worker = workers.SaveChangesWorker(root, [game], {}, write_allowed=True)
    worker.finished.connect(finished.append)
    worker.error.connect(errors.append)

    worker.run()

    assert errors == []
    assert finished
    transactions = read_transactions(root)
    assert transactions[-1]["summary"]["renamed"] == 1
    assert transactions[-1]["changes"] == [
        {
            "type": "name_changed",
            "slot": 2,
            "old_name": "Old Name",
            "new_name": "New Name",
            "product_id": "TST-001",
        }
    ]


def test_save_success_message_is_readable_for_cover_only_change(tmp_path):
    message = workers._save_success_message(
        additions=0,
        deletions=0,
        covers=94,
        menu_items=100,
        backup_path=tmp_path / "backup" / "01",
        log_path=tmp_path / "sd" / "_openmenu_gdemu_manager" / "transactions.jsonl",
    )

    assert message.splitlines()[0] == "Carátulas guardadas en la SD."
    assert "Carátulas sincronizadas: 94." in message
    assert "Juegos agregados" not in message
    assert "Juegos eliminados" not in message
    assert "Backup de 01:" in message
    assert "Registro:" in message


def test_save_transaction_summary_records_product_id_corrections(tmp_path):
    game = GameItem(
        slot=102,
        name="METAL SLUG 6",
        product_id="T0000M",
        artwork_serials=["SLOT106", "T0000M", "SLOT102"],
    )

    summary = workers._save_transaction_summary(
        tmp_path,
        additions=[],
        deletions=[],
        renamed=[],
        covers=[],
        product_updates=[game],
        slot_moves=[],
        before_metadata={102: {"name": "METAL SLUG 6", "product": "SLOT106"}},
    )

    assert summary["summary"]["product_ids_changed"] == 1
    assert summary["changes"] == [
        {
            "type": "product_id_changed",
            "slot": 102,
            "name": "METAL SLUG 6",
            "old_product_id": "SLOT106",
            "new_product_id": "T0000M",
            "artwork_aliases": ["SLOT106", "T0000M", "SLOT102"],
        }
    ]


def test_planned_slot_moves_detects_sparse_menu_slots():
    games = [GameItem(slot=slot, name=f"Game {slot}") for slot in range(2, 15)] + [
        GameItem(slot=16, name="MACROSS"),
        GameItem(slot=100, name="METAL SLUG", product_id="SLOT100"),
    ]

    assert workers._planned_slot_moves(games) == [
        {"old_slot": 16, "new_slot": 15, "name": "MACROSS", "product_id": ""},
        {"old_slot": 100, "new_slot": 16, "name": "METAL SLUG", "product_id": "SLOT100"},
    ]


def test_compact_game_slots_renames_folders_and_updates_synthetic_product_ids(tmp_path):
    root = tmp_path / "sd"
    root.mkdir()
    games = []
    for slot in range(2, 15):
        folder = root / f"{slot:02d}"
        folder.mkdir()
        games.append(GameItem(slot=slot, name=f"Game {slot}", folder=folder, product_id=f"TEST{slot}"))
    slot14 = root / "14"
    slot16 = root / "16"
    slot100 = root / "100"
    slot16.mkdir()
    slot100.mkdir()
    (slot16 / "disc.gdi").write_text("macross", encoding="ascii")
    (slot100 / "disc.cdi").write_text("metal", encoding="ascii")
    games += [
        GameItem(slot=16, name="MACROSS", folder=slot16, product_id="T21501M"),
        GameItem(slot=100, name="METAL SLUG", folder=slot100, product_id="SLOT100"),
    ]

    moves = workers._compact_game_slots(root, games)

    assert moves == [
        {"old_slot": 16, "new_slot": 15, "name": "MACROSS", "product_id": "T21501M"},
        {"old_slot": 100, "new_slot": 16, "name": "METAL SLUG", "product_id": "SLOT100"},
    ]
    assert not slot100.exists()
    assert (root / "15" / "disc.gdi").exists()
    assert (root / "16" / "disc.cdi").exists()
    assert [game.slot for game in games[-2:]] == [15, 16]
    assert games[-1].product_id == "SLOT016"
    assert games[-1].artwork_serials == ["SLOT100", "SLOT016"]
