from openmenu_gdemu_manager.core.models import GameItem
import pytest

from openmenu_gdemu_manager.dreamcast.sd_writer import (
    build_openmenu_text,
    first_free_slot,
    patch_track05_menu,
    validate_track05_menu_capacity,
)


def test_first_free_slot_skips_used_and_pending_deletes():
    games = [
        GameItem(slot=2, name="Used"),
        GameItem(slot=3, name="Deleting", pending_delete=True),
    ]

    assert first_free_slot(games) == 3


def test_build_openmenu_text_contains_slot_entries():
    games = [GameItem(slot=2, name="Sonic Adventure", product_id="MK-51000", region="U")]

    text = build_openmenu_text(games)

    assert "num_items=1" in text
    assert "02.name=Sonic Adventure" in text
    assert "02.product=MK-51000" in text


def test_build_openmenu_text_supports_three_digit_slots():
    games = [GameItem(slot=100, name="Doom Online DC", product_id="DOOMONLINE", region="JUE")]

    text = build_openmenu_text(games)

    assert "num_items=1" in text
    assert "100.name=Doom Online DC" in text
    assert "100.product=DOOMONLINE" in text


def test_validate_track05_menu_capacity_fails_before_patch(tmp_path):
    track = tmp_path / "track05.iso"
    track.write_bytes(b"prefix[OPENMENU]\nold=1\n" + (b"\x00" * 64) + b"suffix")
    games = [GameItem(slot=2, name="A" * 200, product_id="LONGPRODUCT", region="U")]

    with pytest.raises(ValueError, match=r"KB usados.*Detalle tecnico"):
        validate_track05_menu_capacity(track, games)

    assert b"old=1" in track.read_bytes()


def test_patch_track05_menu_uses_same_capacity_validation(tmp_path):
    track = tmp_path / "track05.iso"
    track.write_bytes(b"prefix[OPENMENU]\nold=1\n" + (b" " * 400) + (b"\x00" * 64) + b"suffix")
    games = [GameItem(slot=2, name="Sonic Adventure", product_id="MK-51000", region="U")]

    patch_track05_menu(track, games)

    data = track.read_bytes()
    assert b"02.name=Sonic Adventure" in data
