import json
import os
import urllib.parse
import urllib.request

import pytest


API_BASE_URL = os.environ.get(
    "OPENMENU_COVER_API_URL",
    "https://openmenu-gdemu-cover-api.openmenu-gdemu-manager.workers.dev",
).rstrip("/")


pytestmark = pytest.mark.integration

if os.environ.get("OPENMENU_RUN_INTEGRATION") != "1":
    pytestmark = [
        pytest.mark.integration,
        pytest.mark.skip(reason="set OPENMENU_RUN_INTEGRATION=1 to call the public Cover API"),
    ]


def _get_json(path: str) -> dict:
    request = urllib.request.Request(
        f"{API_BASE_URL}{path}",
        headers={"User-Agent": "openmenu-gdemu-manager-tests", "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _head_or_get(path: str):
    request = urllib.request.Request(
        f"{API_BASE_URL}{path}",
        headers={"User-Agent": "openmenu-gdemu-manager-tests"},
        method="GET",
    )
    return urllib.request.urlopen(request, timeout=20)


def test_cover_api_health_endpoint():
    payload = _get_json("/health")

    assert payload["ok"] is True


def test_cover_api_search_returns_proxied_media_urls_without_credentials():
    query = urllib.parse.quote("Crazy Taxi")
    payload = _get_json(f"/v1/covers/search?system=dreamcast&query={query}")

    assert payload["ok"] is True
    assert payload["results"]

    first = payload["results"][0]
    image_url = first["image_url"]
    serialized = json.dumps(payload).lower()

    assert "/v1/media/" in image_url
    assert "screenscraper.fr" not in image_url
    assert "devid" not in serialized
    assert "devpassword" not in serialized
    assert "sspassword" not in serialized

    media_path = urllib.parse.urlparse(image_url).path
    with _head_or_get(media_path) as response:
        content_type = response.headers.get("Content-Type", "")
        sample = response.read(16)

    assert response.status == 200
    assert content_type.startswith("image/")
    assert sample


@pytest.mark.parametrize('provider_id', ['openmenu', 'libretro', 'community_api'])
def test_production_provider_search_download_and_decode(provider_id, tmp_path, monkeypatch):
    """Opt-in: real application provider/decoder with private isolated cache."""
    import copy
    from openmenu_gdemu_manager.config.settings import DEFAULT_SETTINGS
    from openmenu_gdemu_manager.core.models import GameItem
    from openmenu_gdemu_manager.covers.providers.registry import provider_definitions
    from openmenu_gdemu_manager.covers.providers import base
    from openmenu_gdemu_manager.covers import search
    monkeypatch.setattr(base, 'CACHE_DIR', tmp_path / 'catalogues')
    monkeypatch.setattr(search, 'MANAGER_CACHE_DIR', tmp_path / 'cache')
    settings = copy.deepcopy(DEFAULT_SETTINGS)
    game = GameItem(2, 'Crazy Taxi', product_id='MK51035', region='US')
    provider = provider_definitions()[provider_id]
    assert not provider.requires_credentials and provider.find is not None
    candidates = provider.find(game, game.name, settings)
    assert candidates, f'{provider_id} returned no candidates'
    candidates.sort(key=lambda c: c.score, reverse=True)
    candidate = candidates[0]
    assert candidate.url.startswith('https://')
    assert not any(key in candidate.url.lower() for key in ('devpassword=', 'sspassword=', 'api_key='))
    image = search.load_candidate_image(candidate)
    image.load()
    assert image.width > 0 and image.height > 0
    assert image.mode == 'RGB'
