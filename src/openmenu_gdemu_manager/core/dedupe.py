import hashlib
from pathlib import Path

from PIL import Image, ImageOps

from .image_quality import analyze_image
from .models import Candidate


def enrich_candidate(candidate: Candidate, image_path: Path) -> Candidate:
    with Image.open(image_path) as image:
        rgb = image.convert("RGB")
        candidate.width, candidate.height = rgb.size
        quality = analyze_image(rgb)
        candidate.quality_label = quality.label
        candidate.quality_score = quality.score
        candidate.exact_hash = exact_image_hash(rgb)
        candidate.perceptual_hash = dhash(rgb)
    candidate.cached_path = str(image_path)
    return candidate


def exact_image_hash(image: Image.Image) -> str:
    normalized = ImageOps.contain(image.convert("RGB"), (512, 512), Image.Resampling.LANCZOS)
    return hashlib.sha256(normalized.tobytes()).hexdigest()


def dhash(image: Image.Image, hash_size: int = 8) -> str:
    gray = image.convert("L").resize((hash_size + 1, hash_size), Image.Resampling.LANCZOS)
    bits = []
    for y in range(hash_size):
        for x in range(hash_size):
            bits.append(gray.getpixel((x, y)) > gray.getpixel((x + 1, y)))
    value = 0
    for bit in bits:
        value = (value << 1) | int(bit)
    return f"{value:0{hash_size * hash_size // 4}x}"


def hamming_distance(left: str, right: str) -> int:
    try:
        return (int(left, 16) ^ int(right, 16)).bit_count()
    except ValueError:
        return 64


def dedupe_candidates(candidates: list[Candidate]) -> list[Candidate]:
    unique: list[Candidate] = []
    for candidate in sorted(candidates, key=_candidate_rank, reverse=True):
        duplicate = _find_duplicate(unique, candidate)
        if duplicate is None:
            candidate.duplicate_sources = candidate.duplicate_sources or []
            unique.append(candidate)
            continue
        if candidate.source not in duplicate.duplicate_sources and candidate.source != duplicate.source:
            duplicate.duplicate_sources.append(candidate.source)
        if _candidate_rank(candidate) > _candidate_rank(duplicate):
            candidate.duplicate_sources = sorted(set([duplicate.source, *(duplicate.duplicate_sources or [])]))
            unique[unique.index(duplicate)] = candidate
    return sorted(unique, key=_candidate_rank, reverse=True)


def _find_duplicate(existing: list[Candidate], candidate: Candidate) -> Candidate | None:
    for item in existing:
        if candidate.exact_hash and item.exact_hash and candidate.exact_hash == item.exact_hash:
            return item
        if candidate.perceptual_hash and item.perceptual_hash:
            if hamming_distance(candidate.perceptual_hash, item.perceptual_hash) <= 6:
                return item
    return None


def _candidate_rank(candidate: Candidate) -> tuple[int, int, int, int, int]:
    product = 1 if candidate.product_match else 0
    alias = 1 if candidate.alias_match else 0
    area = candidate.width * candidate.height
    return (product, alias, candidate.score, candidate.quality_score, area)
