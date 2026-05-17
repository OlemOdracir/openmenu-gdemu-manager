from __future__ import annotations

import logging
import urllib.parse
from typing import Any

from ...core.matching import normalize, normalize_product, score_candidate
from ...core.models import Candidate, GameItem
from .base import read_json_url


DEFAULT_COMMUNITY_API_BASE_URL = "https://openmenu-gdemu-cover-api.openmenu-gdemu-manager.workers.dev"
log = logging.getLogger(__name__)


def community_api_candidates(game: GameItem, query: str, settings: dict[str, Any]) -> list[Candidate]:
    cfg = settings.get("cover_providers", {}).get("community_api", {})
    base_url = str(cfg.get("base_url") or DEFAULT_COMMUNITY_API_BASE_URL).strip().rstrip("/")
    if not base_url:
        return []
    _validate_api_base_url(base_url)
    timeout = int(cfg.get("timeout", 20) or 20)
    candidates: list[Candidate] = []
    seen_urls: set[str] = set()
    for search_query in _query_variants(game, query):
        url = f"{base_url}/v1/covers/search?system=dreamcast&query={urllib.parse.quote(search_query)}"
        log.info("Community API search: slot=%03d query=%s request=%s", game.slot, query, search_query)
        payload = read_json_url(url, timeout=timeout)
        if not payload.get("ok"):
            log.warning("Community API returned not-ok payload: slot=%03d request=%s", game.slot, search_query)
            continue
        result_count = len(payload.get("results", []))
        log.info("Community API result count: slot=%03d request=%s count=%d", game.slot, search_query, result_count)
        for item in payload.get("results", []):
            candidate = _candidate_from_item(game, query, search_query, item)
            if candidate is None or candidate.url in seen_urls:
                continue
            seen_urls.add(candidate.url)
            candidates.append(candidate)
        if candidates:
            break
    return candidates


def test_connection(settings: dict[str, Any]) -> dict[str, Any]:
    cfg = settings.get("cover_providers", {}).get("community_api", {})
    base_url = str(cfg.get("base_url") or DEFAULT_COMMUNITY_API_BASE_URL).strip().rstrip("/")
    if not base_url:
        return {"ok": False, "message": "OpenMenu Cover API no tiene URL configurada.", "count": 0}
    _validate_api_base_url(base_url)
    url = f"{base_url}/health"
    payload = read_json_url(url, timeout=int(cfg.get("timeout", 20) or 20))
    ok = bool(payload.get("ok"))
    return {
        "ok": ok,
        "message": "OpenMenu Cover API disponible." if ok else "OpenMenu Cover API no respondio correctamente.",
        "count": 0,
    }


def _validate_api_base_url(base_url: str) -> None:
    parsed = urllib.parse.urlparse(base_url)
    if parsed.scheme.lower() != "https" or not parsed.netloc:
        raise ValueError("OpenMenu Cover API debe usar una URL HTTPS.")


def _query_variants(game: GameItem, query: str) -> list[str]:
    variants: list[str] = []
    for value in (query, _strip_region_suffix(query), game.name, _strip_region_suffix(game.name)):
        cleaned = " ".join(str(value or "").split())
        if cleaned and cleaned.lower() not in {item.lower() for item in variants}:
            variants.append(cleaned)
    return variants


def _strip_region_suffix(value: str) -> str:
    return urllib.parse.unquote(str(value or "")).rsplit("(", 1)[0].strip()


def _candidate_from_item(game: GameItem, query: str, search_query: str, item: dict[str, Any]) -> Candidate | None:
    title = str(item.get("title", "")).strip()
    image_url = str(item.get("image_url") or item.get("thumbnail_url") or "").strip()
    if not title or not image_url:
        return None
    candidate_product = _item_product_id(item)
    product_match = bool(game.product_id and candidate_product and normalize_product(game.product_id) == candidate_product)
    score = max(
        int(item.get("score") or 0),
        score_candidate(query, title, game.product_id, candidate_product),
        score_candidate(search_query, title, game.product_id, candidate_product),
        score_candidate(game.name, title, game.product_id, candidate_product),
    )
    return Candidate(
        title=title,
        source="community_api/screenscraper",
        url=image_url,
        score=score,
        product_match=product_match,
        alias_match=normalize(title) in {normalize(query), normalize(search_query), normalize(game.name)},
        region=str(item.get("region", "")).strip(),
    )


def _item_product_id(item: dict[str, Any]) -> str:
    for key in ("product_id", "serial", "serial_id", "productId"):
        value = normalize_product(str(item.get(key, "")))
        if value:
            return value
    return ""
