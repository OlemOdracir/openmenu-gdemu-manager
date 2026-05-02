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
