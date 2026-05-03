import hashlib
import logging
import urllib.parse
import urllib.request
from io import BytesIO
from pathlib import Path

from PIL import Image

from ..core.dedupe import dedupe_candidates, enrich_candidate
from ..core.matching import has_conflicting_numbers
from ..core.models import Candidate, GameItem
from ..config.paths import MANAGER_CACHE_DIR
from ..services.cover_library import load_saved_candidates, save_candidates
from .providers.base import USER_AGENT
from .providers.registry import (
    iter_enabled_providers,
    provider_threshold,
    source_provider_id,
)
from ..config.settings import load_settings


log = logging.getLogger(__name__)


def find_candidates(
    game: GameItem,
    query: str | None = None,
    include_remote: bool = True,
    enabled_provider_ids: list[str] | set[str] | tuple[str, ...] | None = None,
    manual_mode: bool = False,
) -> list[Candidate]:
    settings = load_settings()
    query = query or game.name
    candidates: list[Candidate] = []
    preload_limit = int(settings.get("dedupe_preload_limit", 90) or 90)
    if settings.get("cover_library_enabled", True):
        try:
            candidates.extend(load_saved_candidates(game))
        except Exception:
            log.exception("Could not load cover library candidates")

    allow_remote = include_remote and bool(settings.get("allow_remote_downloads", True))
    for provider in iter_enabled_providers(settings, include_remote=allow_remote, enabled_provider_ids=enabled_provider_ids):
        candidates.extend(_safe_provider(provider.id, lambda p=provider: p.find(game, query, settings) if p.find else []))

    limit = int(settings.get("candidate_limit", 60) or 60)
    candidates = [
        _normalize_candidate(c, settings)
        for c in candidates
        if not _is_placeholder_candidate(c) and not _has_conflicting_sequence(query, c)
    ]
    candidates = _merge_textual_duplicates(candidates)[:preload_limit]
    enriched = _enrich_for_dedupe(candidates)
    deduped = dedupe_candidates(enriched, exact_only=manual_mode)
    if settings.get("cover_library_enabled", True):
        try:
            save_candidates(game, deduped, query)
        except Exception:
            log.exception("Could not save cover library candidates")
    return _progressive_results(deduped, limit, settings, manual_mode=manual_mode)


def best_auto_candidate(game: GameItem, query: str | None = None, include_remote: bool = True) -> Candidate | None:
    settings = load_settings()
    for candidate in find_candidates(game, query, include_remote):
        if candidate.weak_match:
            continue
        min_auto = provider_threshold(settings, source_provider_id(candidate.source), "min_auto_score", 86)
        if candidate.product_match or candidate.alias_match or candidate.score >= min_auto:
            return candidate
    return None


def load_candidate_image(candidate: Candidate) -> Image.Image:
    if candidate.cached_path and Path(candidate.cached_path).exists():
        return Image.open(candidate.cached_path).convert("RGB")
    if candidate.local_path:
        return Image.open(candidate.local_path).convert("RGB")
    if not candidate.url:
        raise ValueError("Candidate has no image URL")
    cache_file = download_candidate(candidate)
    return Image.open(cache_file).convert("RGB")


def download_candidate(candidate: Candidate) -> Path:
    if candidate.local_path:
        return Path(candidate.local_path)
    parsed = urllib.parse.urlparse(candidate.url)
    name = Path(urllib.parse.unquote(parsed.path)).name or "cover.png"
    digest = hashlib.sha1(candidate.url.encode("utf-8")).hexdigest()[:12]
    safe_stem = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in Path(name).stem).strip("_") or "cover"
    out_dir = MANAGER_CACHE_DIR / "downloads"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{safe_stem}_{digest}.png"
    if out_path.exists():
        return out_path
    req = urllib.request.Request(candidate.url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
    Image.open(BytesIO(data)).convert("RGB").save(out_path, "PNG")
    return out_path


def _safe_provider(name: str, callback) -> list[Candidate]:
    try:
        return callback()
    except Exception:
        log.exception("Provider failed: %s", name)
        return []


def _merge_textual_duplicates(candidates: list[Candidate]) -> list[Candidate]:
    merged: dict[tuple[str, str, str], Candidate] = {}
    for candidate in candidates:
        key = (candidate.source, candidate.title.lower(), candidate.url or candidate.local_path)
        existing = merged.get(key)
        if existing is None or _candidate_text_rank(candidate) > _candidate_text_rank(existing):
            merged[key] = candidate
    return sorted(merged.values(), key=_candidate_text_rank, reverse=True)


def _normalize_candidate(candidate: Candidate, settings: dict) -> Candidate:
    provider_id = source_provider_id(candidate.source)
    min_review = provider_threshold(settings, provider_id, "min_review_score", 65)
    candidate.weak_match = candidate.weak_match or (
        candidate.score < min_review and not candidate.product_match and not candidate.alias_match
    )
    return candidate


def _is_placeholder_candidate(candidate: Candidate) -> bool:
    text = " ".join([candidate.source, candidate.title, candidate.local_path, candidate.url]).lower()
    return "no cover" in text or "no_cover" in text or "placeholder" in text


def _has_conflicting_sequence(query: str, candidate: Candidate) -> bool:
    if candidate.product_match:
        return False
    return has_conflicting_numbers(query, candidate.title)


def _enrich_for_dedupe(candidates: list[Candidate]) -> list[Candidate]:
    enriched: list[Candidate] = []
    for candidate in candidates:
        try:
            image_path = download_candidate(candidate)
            enriched.append(enrich_candidate(candidate, image_path))
        except Exception:
            log.exception("Could not enrich candidate: %s", candidate.display)
            enriched.append(candidate)
    return enriched


def _candidate_text_rank(candidate: Candidate) -> tuple[int, int, int]:
    return (
        1 if candidate.product_match else 0,
        1 if candidate.alias_match else 0,
        candidate.score,
    )


def _progressive_results(candidates: list[Candidate], limit: int, settings: dict, manual_mode: bool = False) -> list[Candidate]:
    def review_threshold(candidate: Candidate) -> int:
        return provider_threshold(settings, source_provider_id(candidate.source), "min_review_score", 65)

    strong = [
        c
        for c in candidates
        if _has_acceptable_preview_quality(c) and (c.product_match or c.alias_match or c.score >= review_threshold(c))
    ]
    if len(strong) >= 6 and not manual_mode:
        return strong[:limit]
    show_weak = manual_mode or settings.get("show_weak_candidates", False)
    if show_weak:
        weak = [c for c in candidates if c not in strong]
        return [*strong, *weak][:limit]
    return strong[:limit]


def _has_acceptable_preview_quality(candidate: Candidate) -> bool:
    if not candidate.quality_score:
        return True
    return candidate.quality_score >= 50

