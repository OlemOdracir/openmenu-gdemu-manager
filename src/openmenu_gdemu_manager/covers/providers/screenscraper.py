from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
from pathlib import Path
from typing import Any

from ...config.paths import MANAGER_CACHE_DIR
from ...core.aliases import is_alias_match, query_variants
from ...core.matching import score_candidate
from ...core.models import Candidate, GameItem
from .base import read_json_url


def screenscraper_candidates(game: GameItem, query: str, settings: dict[str, Any]) -> list[Candidate]:
    cfg = settings.get("cover_providers", {}).get("screenscraper", {})
    _validate_config(cfg)
    api_queries = _api_query_variants(query, game)
    games: list[dict[str, Any]] = []
    seen_games: set[str] = set()
    for api_query in api_queries:
        data = _search_json(api_query, cfg)
        for item in _extract_games(data):
            key = json.dumps(item, sort_keys=True, ensure_ascii=False)
            if key not in seen_games:
                seen_games.add(key)
                games.append(item)
        if games:
            break

    queries: list[str] = []
    for value in [query, game.name, *api_queries]:
        queries.extend(query_variants(value, game.product_id))
    queries = _dedupe_text(queries)
    results: list[Candidate] = []
    for item in games:
        title = _extract_title(item) or query
        media_url = _extract_box_url(item)
        if not media_url:
            continue
        score = max(score_candidate(q, title, game.product_id, "") for q in queries)
        alias_match = any(is_alias_match(q, title) for q in queries)
        if score < 45 and not alias_match:
            continue
        results.append(
            Candidate(
                "screenscraper",
                title,
                score,
                url=media_url,
                source_url=media_url,
                alias_match=alias_match,
                weak_match=score < 70 and not alias_match,
            )
        )
    return results


def _api_query_variants(query: str, game: GameItem) -> list[str]:
    variants: list[str] = []
    for value in (query, game.name):
        text = " ".join(str(value or "").split())
        if not text:
            continue
        split = _split_digit_letter(text)
        spaced = _punctuation_to_spaces(text)
        split_spaced = _split_digit_letter(spaced)
        variants.extend([
            split.title(),
            spaced.title(),
            split_spaced.title(),
            text.title(),
            text,
            split,
            spaced,
            split_spaced,
        ])
    return _dedupe_text([item for item in variants if item], case_sensitive=True)[:8]


def _split_digit_letter(text: str) -> str:
    text = re.sub(r"(?<=\d)(?=[A-Za-z])", " ", text)
    text = re.sub(r"(?<=[A-Za-z])(?=\d)", " ", text)
    return " ".join(text.split())


def _punctuation_to_spaces(text: str) -> str:
    return " ".join(re.sub(r"[-_./]+", " ", text).split())


def _dedupe_text(values: list[str], case_sensitive: bool = False) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = " ".join(str(value or "").split())
        key = clean if case_sensitive else clean.casefold()
        if clean and key not in seen:
            seen.add(key)
            result.append(clean)
    return result


def test_connection(settings: dict[str, Any]) -> dict[str, Any]:
    cfg = settings.get("cover_providers", {}).get("screenscraper", {})
    try:
        _validate_config(cfg)
        data = _search_json("Sonic Adventure", cfg, force_refresh=True)
        count = len([item for item in _extract_games(data) if _extract_box_url(item)])
        return {"ok": True, "message": f"Conexion correcta. Candidatos con media: {count}.", "count": count}
    except Exception as exc:
        return {"ok": False, "message": _friendly_error(exc), "count": 0}


def _validate_config(cfg: dict[str, Any]) -> None:
    resolved = _resolved_config(cfg)
    required = ["base_url", "devid", "devpassword", "softname", "ssid", "sspassword"]
    missing = [key for key in required if not str(resolved.get(key, "")).strip()]
    if missing:
        raise ValueError("Configuracion incompleta: " + ", ".join(missing))


def _search_json(query: str, cfg: dict[str, Any], force_refresh: bool = False) -> dict[str, Any]:
    cfg = _resolved_config(cfg)
    base_url = str(cfg.get("base_url") or "https://api.screenscraper.fr/api2").rstrip("/")
    if urllib.parse.urlparse(base_url).scheme.lower() != "https":
        raise ValueError("ScreenScraper debe usar una URL HTTPS.")
    endpoint = f"{base_url}/jeuRecherche.php"
    params = {
        "devid": str(cfg.get("devid", "")),
        "devpassword": str(cfg.get("devpassword", "")),
        "softname": str(cfg.get("softname", "OpenMenuGDEMUManager")),
        "output": "json",
        "systemeid": str(cfg.get("systemeid", 23)),
        "recherche": query,
    }
    if str(cfg.get("ssid", "")).strip():
        params["ssid"] = str(cfg.get("ssid", "")).strip()
    if str(cfg.get("sspassword", "")).strip():
        params["sspassword"] = str(cfg.get("sspassword", "")).strip()
    url = endpoint + "?" + urllib.parse.urlencode(params)
    cache_path = _cache_path(url)
    if cache_path.exists() and not force_refresh:
        return json.loads(cache_path.read_text(encoding="utf-8"))
    timeout = int(cfg.get("timeout", 30) or 30)
    data = read_json_url(url, timeout=timeout)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


def _resolved_config(cfg: dict[str, Any]) -> dict[str, Any]:
    resolved = dict(cfg)
    resolved["devid"] = str(resolved.get("devid") or os.environ.get("SCREENSCRAPER_DEVID", ""))
    resolved["devpassword"] = str(
        resolved.get("devpassword") or os.environ.get("SCREENSCRAPER_DEVPASSWORD", "")
    )
    return resolved


def _cache_path(url: str) -> Path:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()
    return MANAGER_CACHE_DIR / "api" / "screenscraper" / f"{digest}.json"


def _extract_games(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, dict):
        response = data.get("response")
        if isinstance(response, dict):
            jeux = response.get("jeux") or response.get("jeu")
            if isinstance(jeux, list):
                return [item for item in jeux if isinstance(item, dict)]
            if isinstance(jeux, dict):
                return [jeux]
        for key in ("jeux", "jeu", "games", "game"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
            if isinstance(value, dict):
                return [value]
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


def _extract_title(item: dict[str, Any]) -> str:
    for key in ("nom", "name", "titre", "title"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    names = item.get("noms")
    if isinstance(names, list):
        for row in names:
            if isinstance(row, dict):
                value = row.get("text") or row.get("nom") or row.get("name")
                if isinstance(value, str) and value.strip():
                    return value.strip()
    return ""


def _extract_box_url(item: dict[str, Any]) -> str:
    medias = item.get("medias")
    candidates: list[tuple[int, str]] = []
    _collect_media_urls(medias if medias is not None else item, "", candidates)
    if not candidates:
        return ""
    return sorted(candidates, key=lambda pair: pair[0], reverse=True)[0][1]


def _collect_media_urls(value: Any, context: str, out: list[tuple[int, str]]) -> None:
    if isinstance(value, dict):
        local_context = " ".join(str(value.get(key, "")) for key in ("type", "media", "nom", "name", "region"))
        combined = f"{context} {local_context}".lower()
        for key, raw in value.items():
            if isinstance(raw, str) and raw.startswith(("http://", "https://")) and _looks_like_image(raw, value):
                out.append((_media_score(combined, raw), raw))
            else:
                _collect_media_urls(raw, combined, out)
    elif isinstance(value, list):
        for item in value:
            _collect_media_urls(item, context, out)


def _looks_like_image(url: str, media: dict[str, Any] | None = None) -> bool:
    media = media or {}
    media_format = str(media.get("format", "")).lower()
    if media_format in {"png", "jpg", "jpeg", "webp"}:
        return True
    path = urllib.parse.urlparse(url).path.lower()
    return path.endswith((".png", ".jpg", ".jpeg", ".webp"))


def _media_score(context: str, url: str) -> int:
    text = f"{context} {url}".lower()
    score = 10
    if "box-2d" in text:
        score += 80
    if "box-3d" in text:
        score += 70
    if "box" in text or "cover" in text:
        score += 35
    if "front" in text or "avant" in text:
        score += 20
    if "side" in text or "back" in text or "texture" in text:
        score -= 35
    if "wheel" in text or "sstitle" in text or "screenshot" in text or " ss " in text:
        score -= 50
    if "us" in text or "usa" in text or "wor" in text:
        score += 5
    return score


def _friendly_error(exc: Exception) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        if exc.code == 401:
            return "Credenciales rechazadas por ScreenScraper."
        if exc.code == 429:
            return "ScreenScraper limito la cantidad de peticiones."
        return f"HTTP {exc.code}: {exc.reason}"
    if isinstance(exc, urllib.error.URLError):
        return f"No se pudo conectar: {exc.reason}"
    return str(exc)
