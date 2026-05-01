from pathlib import Path

from PIL import Image

from ...config.settings import configured_local_dirs
from ...core.aliases import is_alias_match, query_variants
from ...core.matching import clean_title_from_filename, normalize_product, score_candidate
from ...core.models import Candidate, GameItem


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}


def local_candidates(game: GameItem, query: str, settings: dict) -> list[Candidate]:
    results: list[Candidate] = []
    product = normalize_product(game.product_id)
    queries = query_variants(query, game.product_id)
    for folder in configured_local_dirs(settings):
        if not folder.exists():
            continue
        for path in folder.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            if _is_placeholder_asset(path) or _looks_like_no_cover_image(path):
                continue
            title = clean_title_from_filename(path.name)
            candidate_product = normalize_product(path.stem.split("_")[0])
            product_match = bool(product and candidate_product == product)
            alias_match = any(is_alias_match(q, title) for q in queries)
            score = max(score_candidate(q, title, game.product_id, candidate_product) for q in queries)
            score = _adjust_local_score(path, score)
            if score >= 45 or product_match or alias_match:
                results.append(
                    Candidate(
                        "local",
                        title,
                        score,
                        source_url=str(path),
                        local_path=str(path),
                        product_match=product_match,
                        alias_match=alias_match,
                        weak_match=score < 70 and not product_match and not alias_match,
                    )
                )
    return results


def _is_placeholder_asset(path: Path) -> bool:
    name = path.stem.lower()
    if name.startswith("no_cover") or name in {"nocover", "placeholder"}:
        return True
    return any(part.lower() == "assets" for part in path.parts) and "cover_manager_cache" in str(path).lower()


def _looks_like_no_cover_image(path: Path) -> bool:
    try:
        with Image.open(path) as image:
            r, g, b = image.convert("RGB").resize((1, 1)).getpixel((0, 0))
            return r > 145 and g < 70 and b < 70
    except Exception:
        return False


def _adjust_local_score(path: Path, score: int) -> int:
    name = path.name.lower()
    if name.endswith("-thumb.png") or path.name.lower() == "front.jpg":
        score = min(100, score + 4)
    if "front" in name or "cover" in name or "box" in name:
        score = min(100, score + 6)
    if "marquee" in name or "disc" in name or "screenshot" in name:
        score = max(0, score - 18)
    return score
