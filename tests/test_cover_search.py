from openmenu_gdemu_manager.core.models import Candidate, GameItem
from openmenu_gdemu_manager.covers.search import find_candidates


def test_disabled_provider_is_not_executed(monkeypatch):
    settings = {
        "cover_providers": {
            "local": {"enabled": False, "priority": 10, "min_review_score": 65},
            "openmenu": {"enabled": False},
            "libretro": {"enabled": False},
            "screenscraper": {"enabled": False},
        },
        "allow_remote_downloads": True,
        "candidate_limit": 60,
        "dedupe_preload_limit": 90,
    }
    monkeypatch.setattr("openmenu_gdemu_manager.covers.search.load_settings", lambda: settings)
    monkeypatch.setattr(
        "openmenu_gdemu_manager.covers.providers.registry.local_candidates",
        lambda *args, **kwargs: [Candidate("local", "Metal Slug 2", 100)],
    )

    assert find_candidates(GameItem(slot=1, name="Metal Slug 2")) == []


def test_single_provider_override_runs_even_if_disabled(monkeypatch):
    settings = {
        "cover_providers": {
            "local": {"enabled": False, "priority": 10, "min_review_score": 65},
        },
        "allow_remote_downloads": True,
        "candidate_limit": 60,
        "dedupe_preload_limit": 90,
    }
    monkeypatch.setattr("openmenu_gdemu_manager.covers.search.load_settings", lambda: settings)
    monkeypatch.setattr(
        "openmenu_gdemu_manager.covers.providers.registry.local_candidates",
        lambda *args, **kwargs: [Candidate("local", "Metal Slug 2", 100)],
    )
    monkeypatch.setattr("openmenu_gdemu_manager.covers.search._enrich_for_dedupe", lambda candidates: candidates)

    candidates = find_candidates(
        GameItem(slot=1, name="Metal Slug 2"),
        enabled_provider_ids=["local"],
    )

    assert len(candidates) == 1
    assert candidates[0].source == "local"


def test_placeholder_candidate_is_filtered(monkeypatch):
    settings = {
        "cover_providers": {
            "local": {"enabled": False, "priority": 10, "min_review_score": 65},
        },
        "allow_remote_downloads": True,
        "candidate_limit": 60,
        "dedupe_preload_limit": 90,
    }
    monkeypatch.setattr("openmenu_gdemu_manager.covers.search.load_settings", lambda: settings)
    monkeypatch.setattr(
        "openmenu_gdemu_manager.covers.providers.registry.local_candidates",
        lambda *args, **kwargs: [Candidate("local", "NO COVER", 100, local_path="no_cover_v2.png")],
    )

    candidates = find_candidates(
        GameItem(slot=1, name="Metal Slug 2"),
        enabled_provider_ids=["local"],
    )

    assert candidates == []


def test_conflicting_sequence_candidate_is_filtered(monkeypatch):
    settings = {
        "cover_providers": {
            "local": {"enabled": False, "priority": 10, "min_review_score": 65},
        },
        "allow_remote_downloads": True,
        "candidate_limit": 60,
        "dedupe_preload_limit": 90,
    }
    monkeypatch.setattr("openmenu_gdemu_manager.covers.search.load_settings", lambda: settings)
    monkeypatch.setattr(
        "openmenu_gdemu_manager.covers.providers.registry.local_candidates",
        lambda *args, **kwargs: [Candidate("local", "Metal Slug 6 PAL", 69)],
    )

    candidates = find_candidates(
        GameItem(slot=15, name="METAL SLUG"),
        enabled_provider_ids=["local"],
    )

    assert candidates == []
