from pathlib import Path

from openmenu_gdemu_manager.dreamcast import scanner
from openmenu_gdemu_manager.dreamcast.scanner import analyze_menu_consistency, scan_sd_root
from openmenu_gdemu_manager.dreamcast.openmenu_dat import DatEntry


def test_scan_prefers_dat_cover_over_legacy_slot_index(monkeypatch, tmp_path):
    root = tmp_path / "sd"
    slot1 = root / "01"
    slot2 = root / "02"
    slot1.mkdir(parents=True)
    slot2.mkdir()
    (slot1 / "track05.bin").write_bytes(b"[OPENMENU]\n02.name=Game\n02.product=T1234M\n" + b"\x00" * 64)

    dat_cover = tmp_path / "dat.png"
    legacy_cover = tmp_path / "legacy.png"

    monkeypatch.setattr(scanner, "load_cover_index_map", lambda: ({2: 7}, {}))
    monkeypatch.setattr(scanner, "_load_openmenu_box_entries", lambda root_path, track_path: {"T1234M": DatEntry("T1234M", b"")})
    monkeypatch.setattr(scanner, "extract_dat_cover", lambda entries, serial, out_path: dat_cover)
    monkeypatch.setattr(scanner, "extract_cover_from_track", lambda track_path, index, out_path: legacy_cover)
    monkeypatch.setattr(scanner, "analyze_image_file", lambda path: None)

    games = scan_sd_root(root, state=None, ini_path=tmp_path / "missing.ini")

    assert len(games) == 1
    assert games[0].current_cover == dat_cover


def test_analyze_menu_consistency_detects_sparse_slots_and_menu_mismatch():
    warnings = analyze_menu_consistency(
        {2, 3, 5, 6},
        {
            2: {"name": "A"},
            3: {"name": "B"},
            4: {"name": "Missing Folder"},
            6: {"name": "D"},
            7: {"name": "Stale Menu"},
        },
    )

    assert warnings[4] == ["menu_entry_without_folder", "missing_physical_slot"]
    assert warnings[5] == ["folder_without_menu_entry", "slot_compaction_needed"]
    assert warnings[6] == ["slot_compaction_needed"]
    assert warnings[7] == ["menu_entry_without_folder"]


def test_scan_marks_games_after_slot_gap_as_pending_repair(monkeypatch, tmp_path):
    root = tmp_path / "sd"
    slot1 = root / "01"
    slot2 = root / "02"
    slot4 = root / "04"
    slot1.mkdir(parents=True)
    slot2.mkdir()
    slot4.mkdir()
    (slot1 / "track05.iso").write_bytes(
        b"[OPENMENU]\n"
        b"02.name=A\n02.product=T0002\n"
        b"04.name=B\n04.product=T0004\n"
        + b"\x00" * 64
    )
    monkeypatch.setattr(scanner, "_load_openmenu_box_entries", lambda root_path, track_path: {})
    monkeypatch.setattr(scanner, "load_cover_index_map", lambda: ({}, {}))
    monkeypatch.setattr(scanner, "read_disc_product_id", lambda folder: "")

    games = scan_sd_root(root, state=None, ini_path=tmp_path / "missing.ini")

    by_slot = {game.slot: game for game in games}
    assert by_slot[2].consistency_warnings == []
    assert by_slot[4].consistency_warnings == ["slot_compaction_needed"]
    assert by_slot[4].save_status == "pendiente_guardar"
