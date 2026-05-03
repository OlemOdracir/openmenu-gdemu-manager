import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from ..config.paths import COVER_LIBRARY_DIR
from ..core.dedupe import enrich_candidate, exact_image_hash
from ..core.image_quality import save_cover_set
from ..core.matching import safe_filename
from ..core.models import Candidate, GameItem


LIBRARY_SCHEMA_VERSION = 1


def load_saved_candidates(game: GameItem) -> list[Candidate]:
    index = _read_index(game)
    candidates: list[Candidate] = []
    for item in index.get("candidates", []):
        candidate = _candidate_from_record(item)
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def candidate_identity(candidate: Candidate) -> str:
    return _candidate_id(candidate)


def count_new_candidates(previous: list[Candidate], current: list[Candidate]) -> int:
    known = {candidate_identity(candidate) for candidate in previous}
    return sum(1 for candidate in current if candidate_identity(candidate) not in known)


def save_candidates(game: GameItem, candidates: list[Candidate], query: str = "") -> None:
    if not candidates:
        return
    game_dir = _game_dir(game)
    images_dir = game_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    index = _read_index(game)
    now = _now()
    records = {str(item.get("id") or _candidate_id_from_record(item)): item for item in index.get("candidates", [])}

    for candidate in candidates:
        image_path = _candidate_image_path(candidate)
        if image_path is None or not image_path.exists():
            continue
        try:
            stored_path, image_hash = _store_image(images_dir, image_path)
        except OSError:
            continue
        candidate.cached_path = str(stored_path)
        candidate.exact_hash = candidate.exact_hash or image_hash
        key = _candidate_id(candidate)
        previous = records.get(key, {})
        record = _candidate_to_record(candidate, stored_path, query, now)
        record["first_seen"] = previous.get("first_seen") or now
        record["selected_count"] = int(previous.get("selected_count") or 0)
        record["last_selected"] = previous.get("last_selected", "")
        records[key] = record

    _write_index(game, _with_candidates(index, records.values(), query, now))


def preserve_existing_cover(game: GameItem, source: str = "current_cover") -> Candidate | None:
    image_path = _existing_cover_path(game)
    if image_path is None:
        return None
    title = game.name or f"Slot {game.slot:03d}"
    candidate = Candidate(
        source=source,
        title=title,
        score=100,
        local_path=str(image_path),
        product_match=bool(game.product_id),
        region=game.region,
    )
    try:
        candidate = enrich_candidate(candidate, image_path)
    except Exception:
        pass
    save_candidates(game, [candidate], query=title)
    return candidate


def persist_selected_cover_to_library(
    game: GameItem,
    candidate: Candidate,
    image: Image.Image,
) -> Candidate:
    game_dir = _game_dir(game)
    selected_dir = game_dir / "selected"
    base_name = f"{safe_filename(game.slot, game.name)}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    original_path, normalized_path, preview_path, quality = save_cover_set(
        image,
        base_name,
        selected_dir / "originals",
        selected_dir / "normalized",
        selected_dir / "preview",
    )
    stored = Candidate(**asdict(candidate))
    stored.local_path = str(original_path)
    stored.cached_path = str(original_path)
    stored.width = quality.width
    stored.height = quality.height
    stored.quality_label = quality.label
    stored.quality_score = quality.score
    stored.exact_hash = exact_image_hash(image)
    stored.perceptual_hash = stored.perceptual_hash
    save_candidates(game, [stored], query=game.name)
    _mark_selected(game, stored, normalized_path, preview_path)
    return stored


def _mark_selected(game: GameItem, candidate: Candidate, normalized_path: Path, preview_path: Path) -> None:
    index = _read_index(game)
    records = {str(item.get("id") or _candidate_id_from_record(item)): item for item in index.get("candidates", [])}
    key = _candidate_id(candidate)
    if key in records:
        now = _now()
        records[key]["selected_count"] = int(records[key].get("selected_count") or 0) + 1
        records[key]["last_selected"] = now
        records[key]["selected_normalized_path"] = str(normalized_path)
        records[key]["selected_preview_path"] = str(preview_path)
        _write_index(game, _with_candidates(index, records.values(), index.get("last_query", ""), now))


def _candidate_from_record(item: dict) -> Candidate | None:
    cached_path = str(item.get("cached_path") or "")
    local_path = str(item.get("local_path") or "")
    if cached_path and not Path(cached_path).exists():
        return None
    if local_path and not Path(local_path).exists():
        local_path = ""
    return Candidate(
        source=str(item.get("source") or "guardada local"),
        title=str(item.get("title") or ""),
        score=int(item.get("score") or 0),
        url=str(item.get("url") or ""),
        source_url=str(item.get("source_url") or ""),
        local_path=local_path,
        cached_path=cached_path,
        product_match=bool(item.get("product_match")),
        alias_match=bool(item.get("alias_match")),
        weak_match=bool(item.get("weak_match")),
        region=str(item.get("region") or ""),
        width=int(item.get("width") or 0),
        height=int(item.get("height") or 0),
        quality_label=str(item.get("quality_label") or ""),
        quality_score=int(item.get("quality_score") or 0),
        exact_hash=str(item.get("exact_hash") or ""),
        perceptual_hash=str(item.get("perceptual_hash") or ""),
        duplicate_sources=list(item.get("duplicate_sources") or []),
    )


def _candidate_to_record(candidate: Candidate, stored_path: Path, query: str, now: str) -> dict:
    record = asdict(candidate)
    record.update(
        {
            "id": _candidate_id(candidate),
            "cached_path": str(stored_path),
            "local_path": str(stored_path),
            "query": query,
            "last_seen": now,
        }
    )
    return record


def _candidate_id(candidate: Candidate) -> str:
    seed = candidate.exact_hash or candidate.url or candidate.local_path or "|".join(
        [candidate.source, candidate.title, candidate.region]
    )
    return exact_image_hash_seed(seed)


def _candidate_id_from_record(record: dict) -> str:
    seed = str(record.get("exact_hash") or record.get("url") or record.get("local_path") or record.get("title") or "")
    return exact_image_hash_seed(seed)


def exact_image_hash_seed(seed: str) -> str:
    import hashlib

    return hashlib.sha256(seed.encode("utf-8", errors="ignore")).hexdigest()[:24]


def _store_image(images_dir: Path, image_path: Path) -> tuple[Path, str]:
    with Image.open(image_path) as image:
        rgb = image.convert("RGB")
        image_hash = exact_image_hash(rgb)
        out_path = images_dir / f"{image_hash[:24]}.png"
        if not out_path.exists():
            rgb.save(out_path, "PNG")
    return out_path, image_hash


def _candidate_image_path(candidate: Candidate) -> Path | None:
    for raw in (candidate.cached_path, candidate.local_path):
        if raw and Path(raw).exists():
            return Path(raw)
    return None


def _existing_cover_path(game: GameItem) -> Path | None:
    for raw in (game.original_image, game.selected_image, str(game.current_cover or "")):
        if raw and Path(raw).exists():
            return Path(raw)
    return None


def _read_index(game: GameItem) -> dict:
    path = _index_path(game)
    if not path.exists():
        return _empty_index(game)
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return _empty_index(game)


def _write_index(game: GameItem, index: dict) -> None:
    path = _index_path(game)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(index, fh, ensure_ascii=False, indent=2, sort_keys=True)
    tmp.replace(path)


def _with_candidates(index: dict, records, query: str, now: str) -> dict:
    index = dict(index)
    index["schema_version"] = LIBRARY_SCHEMA_VERSION
    index["last_query"] = query or index.get("last_query", "")
    index["updated_at"] = now
    index["candidates"] = sorted(records, key=_record_rank, reverse=True)
    return index


def _record_rank(item: dict) -> tuple[int, int, int, int, int]:
    return (
        1 if item.get("product_match") else 0,
        1 if item.get("alias_match") else 0,
        int(item.get("score") or 0),
        int(item.get("quality_score") or 0),
        int(item.get("width") or 0) * int(item.get("height") or 0),
    )


def _empty_index(game: GameItem) -> dict:
    return {
        "schema_version": LIBRARY_SCHEMA_VERSION,
        "game_key": game_library_key(game),
        "slot": game.slot,
        "name": game.name,
        "product_id": game.product_id,
        "region": game.region,
        "created_at": _now(),
        "updated_at": "",
        "last_query": "",
        "candidates": [],
    }


def game_library_key(game: GameItem) -> str:
    parts = [game.product_id.strip(), game.region.strip(), game.name.strip()]
    seed = "|".join(part for part in parts if part) or f"slot-{game.slot:03d}"
    safe = "".join(ch.lower() if ch.isalnum() else "-" for ch in seed)
    while "--" in safe:
        safe = safe.replace("--", "-")
    return safe.strip("-")[:96] or f"slot-{game.slot:03d}"


def _game_dir(game: GameItem) -> Path:
    return COVER_LIBRARY_DIR / "games" / game_library_key(game)


def _index_path(game: GameItem) -> Path:
    return _game_dir(game) / "candidates.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
