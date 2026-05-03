import logging
from pathlib import Path

from PIL import Image

from ..config.paths import INBOX_NORMALIZED_DIR, INBOX_ORIGINALS_DIR, INBOX_PREVIEW_DIR
from ..config.state import update_game_state
from ..core.image_quality import NORMALIZATION_MODE, apply_quality_report, save_cover_set
from ..core.matching import safe_filename
from ..core.models import Candidate, GameItem
from .cover_library import persist_selected_cover_to_library, preserve_existing_cover


log = logging.getLogger(__name__)


def persist_cover_selection(
    game: GameItem,
    candidate: Candidate,
    image: Image.Image,
    quality,
    status: str,
    *,
    state_path: Path,
    state: dict,
    root_path: Path,
    persist_state: bool = True,
) -> Path:
    try:
        preserve_existing_cover(game)
        persist_selected_cover_to_library(game, candidate, image)
    except Exception:
        log.exception("Could not update cover library")
    base_name = safe_filename(game.slot, game.name)
    original_path, normalized_path, preview_path, quality = save_cover_set(
        image,
        base_name,
        INBOX_ORIGINALS_DIR,
        INBOX_NORMALIZED_DIR,
        INBOX_PREVIEW_DIR,
    )
    game.status = status
    game.current_cover = normalized_path
    game.selected_image = str(normalized_path)
    game.original_image = str(original_path)
    game.preview_image = str(preview_path)
    game.selected_source = candidate.source
    game.selected_score = candidate.score
    game.save_status = "pendiente_guardar" if not game.pending_delete else game.save_status
    apply_quality_report(game, quality, NORMALIZATION_MODE)
    if persist_state:
        update_game_state(state_path, state, root_path, game)
    return normalized_path
