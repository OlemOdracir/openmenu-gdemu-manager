from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .. import __version__
from ..core.models import Candidate, GameItem
from .sd_registry import registry_dir


SEARCH_EVENTS_FILE_NAME = "searches.jsonl"


def search_events_path(root: Path) -> Path:
    return registry_dir(root) / SEARCH_EVENTS_FILE_NAME


def sd_root_for_game(game: GameItem) -> Path | None:
    if game.folder is None:
        return None
    folder = Path(game.folder)
    if folder.name.isdigit():
        return folder.parent
    return folder


def append_search_event(root: Path, event: dict[str, Any]) -> Path:
    path = search_events_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "app_version": __version__,
        **event,
    }
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        handle.write("\n")
    return path


def append_search_event_for_game(game: GameItem, event: dict[str, Any]) -> Path | None:
    root = sd_root_for_game(game)
    if root is None:
        return None
    return append_search_event(
        root,
        {
            "slot": game.slot,
            "game_name": game.name,
            "product_id": game.product_id,
            **event,
        },
    )


def summarize_candidates(candidates: list[Candidate], limit: int = 8) -> list[dict[str, Any]]:
    return [
        {
            "title": candidate.title,
            "source": candidate.source,
            "score": candidate.score,
            "quality_score": candidate.quality_score,
            "product_match": candidate.product_match,
            "alias_match": candidate.alias_match,
            "weak_match": candidate.weak_match,
            "url": candidate.url,
        }
        for candidate in candidates[:limit]
    ]
