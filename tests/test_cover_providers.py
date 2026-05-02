from pathlib import Path

from PIL import Image

from openmenu_gdemu_manager.core.matching import score_candidate
from openmenu_gdemu_manager.core.models import Candidate, GameItem
from openmenu_gdemu_manager.covers.providers.local import local_candidates
from openmenu_gdemu_manager.covers.providers.screenscraper import (
    _api_query_variants,
    screenscraper_candidates,
    test_connection as screenscraper_test_connection,
)
from openmenu_gdemu_manager.covers.providers.registry import provider_definitions


def test_local_provider_ignores_no_cover_placeholder(tmp_path: Path):
    placeholder = tmp_path / "no_cover_v2.png"
    Image.new("RGB", (64, 64), "red").save(placeholder)
    real = tmp_path / "Metal Slug 2 front.png"
    Image.new("RGB", (64, 64), "blue").save(real)

    settings = {"local_image_dirs": [str(tmp_path)]}
    game = GameItem(slot=1, name="Metal Slug 2")

    candidates = local_candidates(game, "Metal Slug 2", settings)

    assert [candidate.local_path for candidate in candidates] == [str(real)]


def test_local_provider_ignores_renamed_red_placeholder(tmp_path: Path):
    placeholder = tmp_path / "015 METAL SLUG.png"
    Image.new("RGB", (512, 512), "#b91c1c").save(placeholder)
    settings = {"local_image_dirs": [str(tmp_path)]}

    candidates = local_candidates(GameItem(slot=15, name="METAL SLUG"), "METAL SLUG", settings)

    assert candidates == []


def test_scoring_rejects_sega_rally_for_metal_slug():
    assert score_candidate("Metal Slug 2", "Sega Rally 2") < 65


def test_screenscraper_reports_missing_credentials():
    settings = {"cover_providers": {"screenscraper": {"base_url": "https://api.screenscraper.fr/api2"}}}

    result = screenscraper_test_connection(settings)

    assert result["ok"] is False
    assert "Configuracion incompleta" in result["message"]


def test_screenscraper_parses_media_from_mock(monkeypatch):
    payload = {
        "response": {
            "jeux": [
                {
                    "nom": "Metal Slug 2",
                    "medias": [
                        {"type": "sstitle", "url": "https://example.test/screen.png"},
                        {"type": "box-2D", "region": "us", "url": "https://example.test/box.png"},
                    ],
                }
            ]
        }
    }
    monkeypatch.setattr(
        "openmenu_gdemu_manager.covers.providers.screenscraper._search_json",
        lambda query, cfg, force_refresh=False: payload,
    )
    settings = {
        "cover_providers": {
            "screenscraper": {
                "base_url": "https://api.screenscraper.fr/api2",
                "devid": "dev",
                "devpassword": "pass",
                "softname": "test",
                "ssid": "user",
                "sspassword": "secret",
                "systemeid": 23,
            }
        }
    }

    candidates = screenscraper_candidates(GameItem(slot=1, name="Metal Slug 2"), "Metal Slug 2", settings)

    assert len(candidates) == 1
    assert candidates[0].url == "https://example.test/box.png"
    assert candidates[0].source == "screenscraper"


def test_screenscraper_query_variants_split_digit_letter_title_case():
    game = GameItem(slot=2, name="18WHEELER AMERICAN-PRO-TRUCKER")

    variants = _api_query_variants("18WHEELER", game)

    assert "18 Wheeler" in variants
    assert "18 Wheeler American Pro Trucker" in variants


def test_registry_marks_unimplemented_remote_sources_as_coming_soon():
    definitions = provider_definitions()

    assert definitions["community_api"].find is not None
    assert definitions["community_api"].configurable is False
    assert definitions["screenscraper"].label == "ScreenScraper directo (avanzado)"
    for provider_id in ("mobygames", "igdb", "rawg", "brave_image", "google_image"):
        assert definitions[provider_id].coming_soon is True
        assert definitions[provider_id].configurable is False
