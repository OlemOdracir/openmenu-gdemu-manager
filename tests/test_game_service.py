from openmenu_gdemu_manager.core.models import RomLibraryEntry
from openmenu_gdemu_manager.services.game_service import build_pending_game


def test_build_pending_game_uses_synthetic_product_id_when_disc_has_none():
    entry = RomLibraryEntry(
        name="Phantasy Star Online Ver. 2 (Europe)",
        media_type="CDI",
        source_path="H:/06/disc.cdi",
        product_id="",
    )

    game = build_pending_game(entry, 6)

    assert game.product_id == "SLOT006"


def test_build_pending_game_preserves_real_product_id():
    entry = RomLibraryEntry(
        name="Blue Stinger",
        media_type="GDI",
        source_path="H:/03",
        product_id="T13001D05",
    )

    game = build_pending_game(entry, 3)

    assert game.product_id == "T13001D05"
