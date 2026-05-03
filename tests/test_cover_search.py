from openmenu_gdemu_manager.core.models import Candidate, GameItem
from openmenu_gdemu_manager.covers.search import find_candidates


def _settings_without_cover_library(settings: dict) -> dict:
    return {**settings, "cover_library_enabled": False}


def test_disabled_provider_is_not_executed(monkeypatch):
    settings = _settings_without_cover_library(
        {
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
    )
    monkeypatch.setattr("openmenu_gdemu_manager.covers.search.load_settings", lambda: settings)
    monkeypatch.setattr(
        "openmenu_gdemu_manager.covers.providers.registry.local_candidates",
        lambda *args, **kwargs: [Candidate("local", "Metal Slug 2", 100)],
    )

    assert find_candidates(GameItem(slot=1, name="Metal Slug 2")) == []


def test_single_provider_override_runs_even_if_disabled(monkeypatch):
    settings = _settings_without_cover_library(
        {
            "cover_providers": {
                "local": {"enabled": False, "priority": 10, "min_review_score": 65},
            },
            "allow_remote_downloads": True,
            "candidate_limit": 60,
            "dedupe_preload_limit": 90,
        }
    )
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
    settings = _settings_without_cover_library(
        {
            "cover_providers": {
                "local": {"enabled": False, "priority": 10, "min_review_score": 65},
            },
            "allow_remote_downloads": True,
            "candidate_limit": 60,
            "dedupe_preload_limit": 90,
        }
    )
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
    settings = _settings_without_cover_library(
        {
            "cover_providers": {
                "local": {"enabled": False, "priority": 10, "min_review_score": 65},
            },
            "allow_remote_downloads": True,
            "candidate_limit": 60,
            "dedupe_preload_limit": 90,
        }
    )
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


def test_low_quality_remote_preview_is_not_strong_by_default(monkeypatch):
    settings = _settings_without_cover_library(
        {
            "cover_providers": {
                "community_api": {"enabled": False, "priority": 10, "min_review_score": 65},
            },
            "allow_remote_downloads": True,
            "candidate_limit": 60,
            "dedupe_preload_limit": 90,
        }
    )
    low_quality = Candidate("community_api/screenscraper", "Capcom vs. SNK Millennium Collection", 80)
    low_quality.quality_score = 33
    monkeypatch.setattr("openmenu_gdemu_manager.covers.search.load_settings", lambda: settings)
    monkeypatch.setattr(
        "openmenu_gdemu_manager.covers.providers.community_api.community_api_candidates",
        lambda *args, **kwargs: [low_quality],
    )
    monkeypatch.setattr("openmenu_gdemu_manager.covers.search._enrich_for_dedupe", lambda candidates: candidates)

    candidates = find_candidates(
        GameItem(slot=1, name="Capcom vs. SNK"),
        "capcom vs. SNK",
        enabled_provider_ids=["community_api"],
    )

    assert candidates == []
