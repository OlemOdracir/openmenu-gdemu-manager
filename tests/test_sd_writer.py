from openmenu_gdemu_manager.core.models import GameItem
from openmenu_gdemu_manager.dreamcast.sd_writer import build_openmenu_text, first_free_slot


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
