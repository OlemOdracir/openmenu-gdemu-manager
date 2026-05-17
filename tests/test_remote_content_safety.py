import urllib.error

import pytest

from openmenu_gdemu_manager.covers.providers import base


class _FakeResponse:
    def __init__(self, payload: bytes, content_type: str = "application/json", url: str = "https://api.example.test/data"):
        self._payload = payload
        self._offset = 0
        self.url = url
        self.headers = {"Content-Type": content_type}

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


def test_remote_bytes_rejects_plain_http():
    with pytest.raises(base.RemoteContentError):
        base.read_remote_bytes("http://api.example.test/data", max_bytes=100)


def test_remote_bytes_rejects_large_payload(monkeypatch):
    monkeypatch.setattr(
        base.urllib.request,
        "urlopen",
        lambda request, timeout: _FakeResponse(b"x" * 101),
    )

    with pytest.raises(base.RemoteContentError):
        base.read_remote_bytes("https://api.example.test/data", max_bytes=100)


def test_remote_bytes_retries_temporary_http_errors(monkeypatch):
    calls = {"count": 0}

    def fake_urlopen(request, timeout):
        calls["count"] += 1
        if calls["count"] == 1:
            raise urllib.error.HTTPError(request.full_url, 503, "temporary", {}, None)
        return _FakeResponse(b'{"ok": true}')

    monkeypatch.setattr(base.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(base.time, "sleep", lambda seconds: None)

    assert base.read_json_url("https://api.example.test/data") == {"ok": True}
    assert calls["count"] == 2


def test_remote_bytes_rejects_unexpected_content_type(monkeypatch):
    monkeypatch.setattr(
        base.urllib.request,
        "urlopen",
        lambda request, timeout: _FakeResponse(b"<html></html>", content_type="text/html"),
    )

    with pytest.raises(base.RemoteContentError):
        base.read_image_url("https://api.example.test/cover.png")


def test_remote_bytes_uses_certifi_ssl_context(monkeypatch):
    seen = {}
    fake_context = object()
    monkeypatch.setattr(base, "_default_ssl_context", lambda: fake_context)

    def fake_urlopen(request, timeout, context=None):
        seen["context"] = context
        return _FakeResponse(b'{"ok": true}')

    monkeypatch.setattr(base.urllib.request, "urlopen", fake_urlopen)

    assert base.read_json_url("https://api.example.test/data") == {"ok": True}
    assert seen["context"] is fake_context
