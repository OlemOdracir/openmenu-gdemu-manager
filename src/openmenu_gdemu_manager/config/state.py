import json
from pathlib import Path

from ..core.image_quality import NORMALIZATION_MODE, analyze_image_file, apply_quality_report
from ..core.matching import normalize_product, score_candidate
from ..core.models import GameItem, VALID_STATES


def load_state(path: Path) -> dict:
    if not path.exists():
        return {"games": {}}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if "games" not in data:
            data["games"] = {}
        return data
    except Exception:
        return {"games": {}}


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(state, handle, ensure_ascii=False, indent=2)


def game_key(root: Path, slot: int) -> str:
    return f"{root.resolve()}::{slot:03d}"


def apply_state(game: GameItem, state: dict, root: Path) -> None:
    data = state.get("games", {}).get(game_key(root, game.slot), {})
    if not _state_matches_game(game, data):
        return
    saved_name = (data.get("name") or "").strip()
    if saved_name:
        game.name = saved_name
    if not game.product_id:
        game.product_id = data.get("product_id", "") or ""
    if not game.region:
        game.region = data.get("region", "") or ""
    status = data.get("status")
    if status in VALID_STATES:
        game.status = status
    game.selected_image = data.get("selected_image", "")
    game.original_image = data.get("original_image", "")
    game.preview_image = data.get("preview_image", "")
    game.selected_source = data.get("selected_source", "")
    game.selected_score = int(data.get("selected_score", 0) or 0)
    state_quality_label = data.get("quality_label", "")
    if state_quality_label:
        game.quality_label = state_quality_label
        game.quality_score = int(data.get("quality_score", 0) or 0)
        game.image_width = int(data.get("image_width", 0) or 0)
        game.image_height = int(data.get("image_height", 0) or 0)
        game.normalization_mode = data.get("normalization_mode", "")
    if game.selected_image:
        selected_path = Path(game.selected_image)
        if selected_path.exists():
            game.current_cover = selected_path
            if not game.quality_label:
                source_path = Path(game.original_image) if game.original_image else selected_path
                if not source_path.exists():
                    source_path = selected_path
                report = analyze_image_file(source_path)
                if report is not None:
                    apply_quality_report(game, report, data.get("normalization_mode") or NORMALIZATION_MODE)


def _game_entry(game: GameItem) -> dict:
    return {
        "status": game.status,
        "selected_image": game.selected_image,
        "original_image": game.original_image,
        "preview_image": game.preview_image,
        "selected_source": game.selected_source,
        "selected_score": game.selected_score,
        "quality_label": game.quality_label,
        "quality_score": game.quality_score,
        "image_width": game.image_width,
        "image_height": game.image_height,
        "normalization_mode": game.normalization_mode,
        "name": game.name,
        "product_id": game.product_id,
        "region": game.region,
    }


def _state_matches_game(game: GameItem, data: dict) -> bool:
    if not data:
        return True
    saved_product = normalize_product(data.get("product_id", ""))
    scanned_product = normalize_product(game.product_id)
    if saved_product and scanned_product and saved_product != scanned_product:
        return False
    saved_name = (data.get("name") or "").strip()
    if not saved_product and scanned_product and saved_name and game.name:
        return score_candidate(game.name, saved_name) >= 75
    return True


def flush_state(path: Path, state: dict) -> None:
    save_state(path, state)


def patch_game_state(state: dict, root: Path, game: GameItem) -> None:
    state.setdefault("games", {})[game_key(root, game.slot)] = _game_entry(game)


def drop_game_state(state: dict, root: Path, slot: int) -> None:
    state.setdefault("games", {}).pop(game_key(root, slot), None)


def update_game_state(path: Path, state: dict, root: Path, game: GameItem) -> None:
    patch_game_state(state, root, game)
    save_state(path, state)


def remove_game_state(path: Path, state: dict, root: Path, slot: int) -> None:
    drop_game_state(state, root, slot)
    save_state(path, state)

