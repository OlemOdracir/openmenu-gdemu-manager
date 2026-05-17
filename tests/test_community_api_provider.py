import json
import urllib.error
import urllib.parse

import pytest

from openmenu_gdemu_manager.core.models import GameItem
from openmenu_gdemu_manager.covers.providers import community_api
from openmenu_gdemu_manager.covers.providers import base as provider_base


class _FakeResponse:
    def __init__(self, payload: bytes):
        self._payload = payload
        self._offset = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, size: int = -1) -> bytes:
        if size is None or size < 0:
            size = len(self._payload) - self._offset
        chunk = self._payload[self._offset:self._offset + size]
        self._offset += len(chunk)
        return chunk


def _settings(base_url: str = "https://api.example.test") -> dict:
    return {
        "cover_providers": {
            "community_api": {
                "base_url": base_url,
                "timeout": 5,
            }
        }
    }


def test_community_api_candidates_parse_proxy_results(monkeypatch):
    seen = {}
    payload = {
        "ok": True,
        "results": [
            {
                "title": "Crazy Taxi",
                "image_url": "https://api.example.test/v1/media/abc123",
                "score": 96,
            },
            {"title": "", "image_url": "https://api.example.test/v1/media/empty-title"},
            {"title": "Missing image", "image_url": ""},
        ],
    }

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["timeout"] = timeout
        seen["user_agent"] = request.headers["User-agent"]
        return _FakeResponse(json.dumps(payload).encode("utf-8"))

    monkeypatch.setattr(provider_base.urllib.request, "urlopen", fake_urlopen)

    candidates = community_api.community_api_candidates(GameItem(slot=1, name="Crazy Taxi"), "Crazy Taxi", _settings())

    assert seen["url"] == "https://api.example.test/v1/covers/search?system=dreamcast&query=Crazy%20Taxi"
    assert seen["timeout"] == 5
    assert seen["user_agent"] == "openmenu-cover-manager"
    assert len(candidates) == 1
    assert candidates[0].title == "Crazy Taxi"
    assert candidates[0].url == "https://api.example.test/v1/media/abc123"
    assert candidates[0].source == "community_api/screenscraper"
    assert candidates[0].score == 100


def test_community_api_candidates_return_empty_for_empty_results(monkeypatch):
    monkeypatch.setattr(
        provider_base.urllib.request,
        "urlopen",
        lambda request, timeout: _FakeResponse(b'{"ok": true, "results": []}'),
    )

    candidates = community_api.community_api_candidates(
        GameItem(slot=1, name="Crazy Taxi"),
        "Crazy Taxi",
        _settings(),
    )

    assert candidates == []


def test_community_api_candidates_use_default_base_url_when_config_value_is_blank(monkeypatch):
    seen = {}

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        return _FakeResponse(b'{"ok": true, "results": []}')

    monkeypatch.setattr(provider_base.urllib.request, "urlopen", fake_urlopen)

    candidates = community_api.community_api_candidates(
        GameItem(slot=1, name="Crazy Taxi"),
        "Crazy Taxi",
        {"cover_providers": {"community_api": {"base_url": "", "timeout": 5}}},
    )

    assert candidates == []
    assert seen["url"].startswith("https://openmenu-gdemu-cover-api.openmenu-gdemu-manager.workers.dev/")


def test_community_api_candidates_retry_with_clean_game_name(monkeypatch):
    seen_queries = []

    def fake_urlopen(request, timeout):
        parsed = urllib.parse.urlparse(request.full_url)
        query = urllib.parse.parse_qs(parsed.query)["query"][0]
        seen_queries.append(query)
        if query == "T13001D05":
            return _FakeResponse(b'{"ok": true, "results": []}')
        payload = {
            "ok": True,
            "results": [
                {
                    "title": "Blue Stinger",
                    "image_url": "https://api.example.test/v1/media/blue",
                    "score": 80,
                }
            ],
        }
        return _FakeResponse(json.dumps(payload).encode("utf-8"))

    monkeypatch.setattr(provider_base.urllib.request, "urlopen", fake_urlopen)

    candidates = community_api.community_api_candidates(
        GameItem(slot=3, name="Blue Stinger (United Kingdom)", product_id="T13001D05"),
        "T13001D05",
        _settings(),
    )

    assert seen_queries == ["T13001D05", "Blue Stinger (United Kingdom)"]
    assert len(candidates) == 1
    assert candidates[0].title == "Blue Stinger"
    assert candidates[0].score == 100
    assert candidates[0].alias_match is True


def test_community_api_candidates_return_empty_for_not_ok_payload(monkeypatch):
    monkeypatch.setattr(
        provider_base.urllib.request,
        "urlopen",
        lambda request, timeout: _FakeResponse(b'{"ok": false, "results": []}'),
    )

    candidates = community_api.community_api_candidates(GameItem(slot=1, name="Crazy Taxi"), "Crazy Taxi", _settings())

    assert candidates == []


def test_community_api_candidates_propagate_network_errors(monkeypatch):
    def fake_urlopen(request, timeout):
        raise urllib.error.URLError("timeout")

    monkeypatch.setattr(provider_base.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(urllib.error.URLError):
        community_api.community_api_candidates(GameItem(slot=1, name="Crazy Taxi"), "Crazy Taxi", _settings())


def test_community_api_connection_uses_health_endpoint(monkeypatch):
    seen = {}

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        return _FakeResponse(b'{"ok": true}')

    monkeypatch.setattr(provider_base.urllib.request, "urlopen", fake_urlopen)

    result = community_api.test_connection(_settings("https://api.example.test/"))

    assert seen["url"] == "https://api.example.test/health"
    assert result == {"ok": True, "message": "OpenMenu Cover API disponible.", "count": 0}
