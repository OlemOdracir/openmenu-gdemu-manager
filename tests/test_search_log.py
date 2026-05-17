import json

from openmenu_gdemu_manager.core.models import Candidate, GameItem
from openmenu_gdemu_manager.services.search_log import (
    append_search_event_for_game,
    sd_root_for_game,
    summarize_candidates,
)


def test_sd_root_for_game_uses_numeric_slot_parent(tmp_path):
    slot = tmp_path / "03"
    slot.mkdir()
    game = GameItem(slot=3, name="Blue Stinger", folder=slot)

    assert sd_root_for_game(game) == tmp_path


def test_append_search_event_for_game_writes_sd_jsonl(tmp_path):
    slot = tmp_path / "03"
    slot.mkdir()
    game = GameItem(slot=3, name="Blue Stinger", product_id="T13001D05", folder=slot)

    path = append_search_event_for_game(game, {"event": "candidate_search", "query": "Blue", "result_count": 1})

    assert path == tmp_path / "_openmenu_gdemu_manager" / "searches.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["event"] == "candidate_search"
    assert rows[0]["slot"] == 3
    assert rows[0]["game_name"] == "Blue Stinger"
    assert rows[0]["product_id"] == "T13001D05"
    assert rows[0]["query"] == "Blue"
    assert rows[0]["result_count"] == 1


def test_summarize_candidates_limits_search_log_payload():
    candidates = [Candidate("community_api/screenscraper", f"Game {index}", 90 + index) for index in range(3)]

    summary = summarize_candidates(candidates, limit=2)

    assert summary == [
        {
            "title": "Game 0",
            "source": "community_api/screenscraper",
            "score": 90,
            "quality_score": 0,
            "product_match": False,
            "alias_match": False,
            "weak_match": False,
            "url": "",
        },
        {
            "title": "Game 1",
            "source": "community_api/screenscraper",
            "score": 91,
            "quality_score": 0,
            "product_match": False,
            "alias_match": False,
            "weak_match": False,
            "url": "",
        },
    ]
