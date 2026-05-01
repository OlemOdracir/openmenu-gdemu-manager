import csv

from ...core.aliases import is_alias_match, query_variants
from ...core.matching import clean_title_from_filename, normalize_product, score_candidate
from ...core.models import Candidate, GameItem
from .base import is_image_path, read_json_cache, read_text_cache


OPENMENU_API_ROOT = "https://api.github.com/repos/mrneo240/openMenu_imagedb/contents"
OPENMENU_FOLDERS = [
    "USA_input",
    "PAL_input",
    "JAP_input",
    "HB_input",
    "EX_input",
    "AW_NTSC_input",
    "AW_PAL_input",
]


def openmenu_candidates(game: GameItem, query: str) -> list[Candidate]:
    out: list[Candidate] = []
    product_to_names = _openmenu_product_names()
    product = normalize_product(game.product_id)
    product_names = product_to_names.get(product, set())
    queries = query_variants(query, game.product_id)

    for folder in OPENMENU_FOLDERS:
        data = read_json_cache(f"openmenu_{folder}.json", f"{OPENMENU_API_ROOT}/{folder}")
        for entry in data:
            name = entry.get("name", "")
            if not is_image_path(name):
                continue
            title = clean_title_from_filename(name)
            product_match = name in product_names
            alias_match = any(is_alias_match(q, title) for q in queries)
            score = 100 if product_match else max(score_candidate(q, title, game.product_id, "") for q in queries)
            if score >= 45 or product_match or alias_match:
                out.append(
                    Candidate(
                        f"openMenu/{folder}",
                        title,
                        score,
                        url=entry.get("download_url", ""),
                        source_url=entry.get("html_url", "") or entry.get("download_url", ""),
                        product_match=product_match,
                        alias_match=alias_match,
                        weak_match=score < 70 and not product_match and not alias_match,
                    )
                )
    return out


def _openmenu_product_names() -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    try:
        catalogues = read_json_cache("openmenu_catalogues.json", f"{OPENMENU_API_ROOT}/catalogues")
        for entry in catalogues:
            if not entry.get("name", "").lower().endswith(".csv"):
                continue
            text = read_text_cache(f"openmenu_catalogue_{entry['name']}", entry["download_url"])
            for row in csv.reader(text.splitlines()):
                if len(row) < 2:
                    continue
                image_name = row[0].strip().replace(".pvr", ".png")
                product = normalize_product(row[1].strip().replace(".pvr", ""))
                if product:
                    result.setdefault(product, set()).add(image_name)
    except Exception:
        return result
    return result

