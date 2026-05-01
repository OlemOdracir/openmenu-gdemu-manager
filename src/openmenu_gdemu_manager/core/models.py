from dataclasses import dataclass
from pathlib import Path


VALID_STATES = {"no_revisada", "correcta", "dudosa", "faltante", "seleccionada"}


@dataclass
class GameItem:
    slot: int
    name: str
    product_id: str = ""
    region: str = ""
    disc: str = ""
    vga: str = ""
    version: str = ""
    date: str = ""
    media_type: str = ""
    folder: Path | None = None
    cover_index: int | None = None
    current_cover: Path | None = None
    status: str = "no_revisada"
    selected_image: str = ""
    original_image: str = ""
    preview_image: str = ""
    selected_source: str = ""
    selected_score: int = 0
    quality_label: str = ""
    quality_score: int = 0
    image_width: int = 0
    image_height: int = 0
    normalization_mode: str = ""
    source_path: str = ""
    is_new: bool = False
    pending_delete: bool = False
    pending_add: bool = False
    has_placeholder_cover: bool = False
    save_status: str = ""


@dataclass
class Candidate:
    source: str
    title: str
    score: int
    url: str = ""
    source_url: str = ""
    local_path: str = ""
    cached_path: str = ""
    product_match: bool = False
    alias_match: bool = False
    weak_match: bool = False
    width: int = 0
    height: int = 0
    quality_label: str = ""
    quality_score: int = 0
    exact_hash: str = ""
    perceptual_hash: str = ""
    duplicate_sources: list[str] | None = None

    @property
    def display(self) -> str:
        if self.product_match:
            mark = "ID"
        elif self.alias_match:
            mark = "AL"
        elif self.weak_match:
            mark = "WK"
        else:
            mark = "NM"
        sources = self.source
        if self.duplicate_sources:
            sources = f"{sources} +{len(self.duplicate_sources)}"
        return f"{self.score:03d} | {mark} | {sources} | {self.title}"


@dataclass
class BulkProposal:
    slot: int
    candidate: Candidate | None = None
    image: object | None = None
    quality: object | None = None
    status: str = ""
    reason: str = ""


@dataclass
class RomLibraryEntry:
    name: str
    media_type: str
    source_path: str
    product_id: str = ""
    region: str = ""
    disc: str = "1/1"
    vga: str = "1"
    version: str = ""
    date: str = ""
    existing_match: bool = False
    cover_path: str = ""
