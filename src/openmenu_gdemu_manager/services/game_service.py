from ..core.models import GameItem, RomLibraryEntry
from ..dreamcast.sd_writer import first_free_slot


def next_free_slot(games: list[GameItem]) -> int | None:
    return first_free_slot(games)


def build_pending_game(entry: RomLibraryEntry, slot: int, cover_index: int | None = None) -> GameItem:
    return GameItem(
        slot=slot,
        name=entry.name,
        product_id=entry.product_id,
        region=entry.region,
        disc=entry.disc or "1/1",
        vga=entry.vga or "1",
        version=entry.version,
        date=entry.date,
        media_type=entry.media_type,
        source_path=entry.source_path,
        status="faltante",
        is_new=True,
        pending_add=True,
        save_status="pendiente_guardar",
        cover_index=cover_index,
    )
