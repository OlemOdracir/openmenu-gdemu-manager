from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any

from ...core.matching import score_candidate
from ...core.models import Candidate, GameItem
from .base import USER_AGENT


def community_api_candidates(game: GameItem, query: str, settings: dict[str, Any]) -> list[Candidate]:
    cfg = settings.get("cover_providers", {}).get("community_api", {})
    base_url = str(cfg.get("base_url", "")).strip().rstrip("/")
    if not base_url:
        return []
    url = f"{base_url}/v1/covers/search?system=dreamcast&query={urllib.parse.quote(query)}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=int(cfg.get("timeout", 20) or 20)) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not payload.get("ok"):
        return []
    candidates: list[Candidate] = []
    for item in payload.get("results", []):
        title = str(item.get("title", "")).strip()
        image_url = str(item.get("image_url", "")).strip()
        if not title or not image_url:
            continue
        score = int(item.get("score") or score_candidate(query, title))
        candidates.append(
            Candidate(
                title=title,
                source="community_api/screenscraper",
                url=image_url,
                score=score,
            )
        )
    return candidates


def test_connection(settings: dict[str, Any]) -> dict[str, Any]:
    cfg = settings.get("cover_providers", {}).get("community_api", {})
    base_url = str(cfg.get("base_url", "")).strip().rstrip("/")
    if not base_url:
        return {"ok": False, "message": "OpenMenu Cover API no tiene URL configurada.", "count": 0}
    url = f"{base_url}/health"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=int(cfg.get("timeout", 20) or 20)) as response:
        payload = json.loads(response.read().decode("utf-8"))
    ok = bool(payload.get("ok"))
    return {
        "ok": ok,
        "message": "OpenMenu Cover API disponible." if ok else "OpenMenu Cover API no respondio correctamente.",
        "count": 0,
    }
