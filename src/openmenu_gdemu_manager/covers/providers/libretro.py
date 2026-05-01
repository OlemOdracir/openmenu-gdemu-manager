from ...core.aliases import is_alias_match, query_variants
from ...core.matching import clean_title_from_filename, score_candidate
from ...core.models import Candidate, GameItem
from .base import is_image_path, read_json_cache


LIBRETRO_API = "https://api.github.com/repos/libretro-thumbnails/Sega_-_Dreamcast/contents/Named_Boxarts"


def libretro_candidates(game: GameItem, query: str) -> list[Candidate]:
    out: list[Candidate] = []
    data = read_json_cache("libretro_named_boxarts.json", LIBRETRO_API)
    queries = query_variants(query, game.product_id)
    for entry in data:
        name = entry.get("name", "")
        if not is_image_path(name):
            continue
        title = clean_title_from_filename(name)
        alias_match = any(is_alias_match(q, title) for q in queries)
        score = max(score_candidate(q, title, game.product_id, "") for q in queries)
        if score >= 45 or alias_match:
            out.append(
                Candidate(
                    "libretro",
                    title,
                    score,
                    url=entry.get("download_url", ""),
                    source_url=entry.get("html_url", "") or entry.get("download_url", ""),
                    alias_match=alias_match,
                    weak_match=score < 70 and not alias_match,
                )
            )
    return out

