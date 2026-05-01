from openmenu_gdemu_manager.config.state import apply_state
from openmenu_gdemu_manager.core.models import GameItem
from openmenu_gdemu_manager.dreamcast.metadata import (
    parse_openmenu_from_track,
    parse_openmenu_ini,
    parse_openmenu_text,
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


def test_read_name_txt_strips_utf8_bom(tmp_path):
    folder = tmp_path / "02"
    folder.mkdir()
    (folder / "name.txt").write_bytes(b"\xef\xbb\xbfDaytona USA\n")

    assert read_name_txt(folder) == "Daytona USA"
