import re
from difflib import SequenceMatcher
from pathlib import Path


STRICT_TOKENS = {"ver", "part", "plus", "pro", "championship", "round", "volume"}


def strip_disc(text: str) -> str:
    text = re.sub(r"\s*\[Disc\s+\d+\]\s*", " ", text, flags=re.I)
    text = re.sub(r"\s*\(Disc\s+\d+\s+of\s+\d+\)\s*", " ", text, flags=re.I)
    return " ".join(text.split())


def clean_title_from_filename(name: str) -> str:
    stem = Path(name).stem
    stem = re.sub(r"-(image|thumb|marquee)$", "", stem, flags=re.I)
    stem = re.sub(r"\.(pvr|png|jpg|jpeg)$", "", stem, flags=re.I)
    return " ".join(stem.replace("_", " ").split())


def normalize(text: str) -> str:
    text = strip_disc(text).lower()
    text = text.replace("&", " and ")
    text = text.replace("'", "")
    text = re.sub(r"\bdreamcast\b", " ", text)
    text = re.sub(
        r"\b(sega|usa|europe|japan|germany|united kingdom|world|ntsc|pal|rev|en|fr|de|es|it|nl|ja)\b",
        " ",
        text,
    )
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\bver\s*2\b", " ver 2 ", text)
    return " ".join(text.split())


def score_candidate(query: str, title: str, product_id: str = "", candidate_product: str = "") -> int:
    product_id = normalize_product(product_id)
    candidate_product = normalize_product(candidate_product)
    if product_id and candidate_product and product_id == candidate_product:
        return 100

    nq = normalize(query)
    nt = normalize(title)
    if not nq or not nt:
        return 0

    ratio = int(SequenceMatcher(None, nq, nt).ratio() * 100)
    q_tokens = set(nq.split())
    t_tokens = set(nt.split())
    overlap = int((len(q_tokens & t_tokens) / max(1, len(q_tokens))) * 100)
    score = int((ratio * 0.55) + (overlap * 0.45))

    q_numbers = {tok for tok in q_tokens if tok.isdigit()}
    t_numbers = {tok for tok in t_tokens if tok.isdigit()}
    missing_numbers = q_numbers - t_tokens
    extra_numbers = t_numbers - q_numbers
    missing_strict = (STRICT_TOKENS & q_tokens) - t_tokens

    if nq == nt:
        score = 100
    if (nq in nt or nt in nq) and not missing_numbers and not missing_strict and not extra_numbers:
        score = max(score, 92)
    if missing_numbers:
        score -= 30 * len(missing_numbers)
    if extra_numbers:
        score -= 25 * len(extra_numbers)
    if missing_strict:
        score -= 12 * len(missing_strict)
    return max(0, min(100, score))


def has_conflicting_numbers(query: str, title: str) -> bool:
    nq = normalize(query)
    nt = normalize(title)
    if not nq or not nt:
        return False
    q_tokens = set(nq.split())
    t_tokens = set(nt.split())
    q_numbers = {tok for tok in q_tokens if tok.isdigit()}
    t_numbers = {tok for tok in t_tokens if tok.isdigit()}
    if q_numbers and t_numbers:
        return q_numbers != t_numbers
    if not q_numbers and t_numbers:
        shared = q_tokens & t_tokens
        return len(shared) >= max(1, min(2, len(q_tokens)))
    return False


def normalize_product(product_id: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (product_id or "").upper())


def safe_filename(slot: int, title: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9]+", "_", strip_disc(title)).strip("_")
    return f"{slot:03d}_{safe or 'cover'}.png"
