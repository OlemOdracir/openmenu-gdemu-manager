from openmenu_gdemu_manager.config.state import apply_state
from openmenu_gdemu_manager.core.models import GameItem
from openmenu_gdemu_manager.dreamcast.metadata import (
    artwork_serial_candidates,
    find_openmenu_track,
    menu_product_id_for_slot,
    parse_openmenu_from_track,
    parse_openmenu_ini,
    parse_openmenu_text,
    read_disc_product_id,
    read_name_txt,
)


def test_parse_openmenu_ini_reads_slot_items(tmp_path):
    ini = tmp_path / "OPENMENU.current.generated.ini"
    ini.write_text(
        "[OPENMENU]\n"
        "num_items=1\n"
        "[ITEMS]\n"
        "02.name=Sonic Adventure\n"
        "02.product=MK-51000\n",
        encoding="utf-8",
    )

    parsed = parse_openmenu_ini(ini)

    assert parsed[2]["name"] == "Sonic Adventure"
    assert parsed[2]["product"] == "MK-51000"


def test_parse_openmenu_text_reads_zero_padded_slots():
    parsed = parse_openmenu_text(
        "[OPENMENU]\n"
        "07.name=DEAD OR ALIVE 2\n"
        "07.region=J\n"
        "07.product=T3601M\n"
    )

    assert parsed[7]["region"] == "J"
    assert parsed[7]["product"] == "T3601M"


def test_parse_openmenu_from_track_reads_embedded_block(tmp_path):
    track = tmp_path / "track05.iso"
    track.write_bytes(
        b"header"
        + b"[OPENMENU]\n08.name=Fatal Fury - Mark of the Wolves\n08.region=U\n08.product=T44306N\n"
        + (b"\x00" * 64)
        + b"tail"
    )

    parsed = parse_openmenu_from_track(track)

    assert parsed[8]["name"] == "Fatal Fury - Mark of the Wolves"
    assert parsed[8]["region"] == "U"
    assert parsed[8]["product"] == "T44306N"


def test_find_openmenu_track_uses_last_data_track_declared_by_gdi(tmp_path):
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
    (slot1 / "track05.bin").write_bytes(b"data [OPENMENU] openMenu NEODC_1")

    assert find_openmenu_track(tmp_path) == slot1 / "track05.bin"


def test_apply_state_fills_missing_metadata_without_overriding_scan(tmp_path):
    root = tmp_path / "sd"
    root.mkdir()
    state = {
        "games": {
            f"{root.resolve()}::007": {
                "name": "DEAD OR ALIVE 2",
                "product_id": "T3601M",
                "region": "J",
            }
        }
    }

    missing = GameItem(slot=7, name="DEAD OR ALIVE 2")
    apply_state(missing, state, root)
    assert missing.product_id == "T3601M"
    assert missing.region == "J"

    scanned = GameItem(slot=7, name="DEAD OR ALIVE 2", product_id="SCANID", region="U")
    apply_state(scanned, state, root)
    assert scanned.product_id == "SCANID"
    assert scanned.region == "U"


def test_apply_state_ignores_stale_slot_metadata(tmp_path):
    root = tmp_path / "sd"
    root.mkdir()
    state = {
        "games": {
            f"{root.resolve()}::003": {
                "name": "Alice's Moms Rescue",
                "product_id": "",
                "status": "seleccionada",
                "selected_image": "old.png",
            },
            f"{root.resolve()}::004": {
                "name": "Alien Front Online",
                "product_id": "MK51171",
                "status": "seleccionada",
                "selected_image": "old.png",
            },
        }
    }

    game_without_saved_product = GameItem(slot=3, name="Capcom vs. SNK Pro", product_id="T1247M")
    apply_state(game_without_saved_product, state, root)
    assert game_without_saved_product.status == "no_revisada"
    assert game_without_saved_product.selected_image == ""

    game_with_wrong_saved_product = GameItem(slot=4, name="Capcom vs. SNK", product_id="T1218N")
    apply_state(game_with_wrong_saved_product, state, root)
    assert game_with_wrong_saved_product.status == "no_revisada"
    assert game_with_wrong_saved_product.selected_image == ""


def test_apply_state_does_not_override_scanned_current_cover(tmp_path):
    root = tmp_path / "sd"
    root.mkdir()
    scanned_cover = tmp_path / "scanned.png"
    cached_cover = tmp_path / "cached.png"
    scanned_cover.write_bytes(b"scanned")
    cached_cover.write_bytes(b"cached")
    state = {
        "games": {
            f"{root.resolve()}::007": {
                "name": "DEAD OR ALIVE 2",
                "product_id": "T3601M",
                "selected_image": str(cached_cover),
            }
        }
    }

    game = GameItem(slot=7, name="DEAD OR ALIVE 2", product_id="T3601M", current_cover=scanned_cover)
    apply_state(game, state, root)

    assert game.current_cover == scanned_cover
    assert game.selected_image == str(cached_cover)


def test_apply_state_accepts_saved_product_that_matches_artwork_alias(tmp_path):
    root = tmp_path / "sd"
    root.mkdir()
    cached_cover = tmp_path / "cached.png"
    cached_cover.write_bytes(b"cached")
    state = {
        "games": {
            f"{root.resolve()}::102": {
                "name": "METAL SLUG 6",
                "product_id": "SLOT106",
                "selected_image": str(cached_cover),
            }
        }
    }

    game = GameItem(
        slot=102,
        name="METAL SLUG 6",
        product_id="T0000M",
        artwork_serials=["SLOT106", "T0000M", "SLOT102"],
    )
    apply_state(game, state, root)

    assert game.product_id == "T0000M"
    assert game.selected_image == str(cached_cover)


def test_read_name_txt_strips_utf8_bom(tmp_path):
    folder = tmp_path / "02"
    folder.mkdir()
    (folder / "name.txt").write_bytes(b"\xef\xbb\xbfDaytona USA\n")

    assert read_name_txt(folder) == "Daytona USA"


def test_read_disc_product_id_reads_ip_bin_from_declared_gdi_track(tmp_path):
    folder = tmp_path / "102"
    folder.mkdir()
    (folder / "disc.gdi").write_text(
        "\n".join(["2", "1 0 4 2048 track01.iso 0", "2 45000 4 2048 track03.iso 0"]),
        encoding="ascii",
    )
    ip = bytearray(0x60)
    ip[:16] = b"SEGA SEGAKATANA "
    ip[0x40:0x50] = b"T0000M    V1.000"
    (folder / "track03.iso").write_bytes(bytes(ip))

    assert read_disc_product_id(folder) == "T0000M"


def test_menu_product_id_prefers_real_disc_serial_and_repairs_synthetic_slot_id():
    assert menu_product_id_for_slot(102, "SLOT106", "T0000M") == "T0000M"
    assert menu_product_id_for_slot(102, "SLOT106", "") == "SLOT102"
    assert menu_product_id_for_slot(7, "T3601M", "") == "T3601M"


def test_artwork_serial_candidates_keep_old_synthetic_alias_while_adding_clean_ids():
    assert artwork_serial_candidates(102, "SLOT106", "T0000M", "T0000M") == [
        "SLOT106",
        "T0000M",
        "SLOT102",
    ]
