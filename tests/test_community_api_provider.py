import json
import urllib.error

import pytest

from openmenu_gdemu_manager.core.models import GameItem
from openmenu_gdemu_manager.covers.providers import community_api


class _FakeResponse:
    def __init__(self, payload: bytes):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return self._payload


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

    monkeypatch.setattr(community_api.urllib.request, "urlopen", fake_urlopen)

    candidates = community_api.community_api_candidates(GameItem(slot=1, name="Crazy Taxi"), "Crazy Taxi", _settings())

    assert seen["url"] == "https://api.example.test/v1/covers/search?system=dreamcast&query=Crazy%20Taxi"
    assert seen["timeout"] == 5
    assert seen["user_agent"] == "openmenu-cover-manager"
    assert len(candidates) == 1
    assert candidates[0].title == "Crazy Taxi"
    assert candidates[0].url == "https://api.example.test/v1/media/abc123"
    assert candidates[0].source == "community_api/screenscraper"
    assert candidates[0].score == 96


def test_community_api_candidates_return_empty_when_disabled():
    candidates = community_api.community_api_candidates(
        GameItem(slot=1, name="Crazy Taxi"),
        "Crazy Taxi",
        {"cover_providers": {"community_api": {"base_url": ""}}},
    )

    assert candidates == []


def test_community_api_candidates_return_empty_for_not_ok_payload(monkeypatch):
    monkeypatch.setattr(
        community_api.urllib.request,
        "urlopen",
        lambda request, timeout: _FakeResponse(b'{"ok": false, "results": []}'),
    )

    candidates = community_api.community_api_candidates(GameItem(slot=1, name="Crazy Taxi"), "Crazy Taxi", _settings())

    assert candidates == []


def test_community_api_candidates_propagate_network_errors(monkeypatch):
    def fake_urlopen(request, timeout):
        raise urllib.error.URLError("timeout")

    monkeypatch.setattr(community_api.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(urllib.error.URLError):
        community_api.community_api_candidates(GameItem(slot=1, name="Crazy Taxi"), "Crazy Taxi", _settings())


def test_community_api_connection_uses_health_endpoint(monkeypatch):
    seen = {}

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        return _FakeResponse(b'{"ok": true}')

    monkeypatch.setattr(community_api.urllib.request, "urlopen", fake_urlopen)

    result = community_api.test_connection(_settings("https://api.example.test/"))

    assert seen["url"] == "https://api.example.test/health"
    assert result == {"ok": True, "message": "OpenMenu Cover API disponible.", "count": 0}
