from pathlib import Path

from PIL import Image

from openmenu_gdemu_manager.core.image_quality import analyze_image
from openmenu_gdemu_manager.core.models import Candidate, GameItem
from openmenu_gdemu_manager.covers.search import find_candidates
from openmenu_gdemu_manager.services.cover_library import count_new_candidates, load_saved_candidates, save_candidates
from openmenu_gdemu_manager.services.cover_service import persist_cover_selection


def _image(path: Path, color: tuple[int, int, int]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (512, 512), color).save(path, "PNG")
    return path


def test_saved_candidates_are_loaded_without_online_provider(tmp_path, monkeypatch):
    monkeypatch.setattr("openmenu_gdemu_manager.services.cover_library.COVER_LIBRARY_DIR", tmp_path / "library")
    settings = {
        "cover_providers": {
            "local": {"enabled": False, "priority": 10, "min_review_score": 65},
            "openmenu": {"enabled": False},
            "libretro": {"enabled": False},
            "screenscraper": {"enabled": False},
        },
        "allow_remote_downloads": True,
        "candidate_limit": 60,
        "dedupe_preload_limit": 90,
        "cover_library_enabled": True,
    }
    monkeypatch.setattr("openmenu_gdemu_manager.covers.search.load_settings", lambda: settings)
    game = GameItem(slot=3, name="Capcom vs. SNK", product_id="T1234M")
    cover = _image(tmp_path / "covers" / "capcom.png", (200, 20, 20))
    save_candidates(game, [Candidate("openmenu", "Capcom vs. SNK (USA)", 100, local_path=str(cover))], "capcom vs snk")

    candidates = find_candidates(game, "capcom vs snk", include_remote=False)

    assert len(candidates) == 1
    assert candidates[0].title == "Capcom vs. SNK (USA)"
    assert Path(candidates[0].cached_path).exists()


def test_new_search_results_are_appended_to_saved_candidates(tmp_path, monkeypatch):
    monkeypatch.setattr("openmenu_gdemu_manager.services.cover_library.COVER_LIBRARY_DIR", tmp_path / "library")
    settings = {
        "cover_providers": {
            "local": {"enabled": False, "priority": 10, "min_review_score": 65},
        },
        "allow_remote_downloads": True,
        "candidate_limit": 60,
        "dedupe_preload_limit": 90,
        "cover_library_enabled": True,
    }
    monkeypatch.setattr("openmenu_gdemu_manager.covers.search.load_settings", lambda: settings)
    game = GameItem(slot=48, name="SPIDER-MAN", product_id="T13008N")
    first = _image(tmp_path / "covers" / "usa.png", (210, 10, 10))
    second = _image(tmp_path / "covers" / "pal.png", (10, 10, 210))
    save_candidates(game, [Candidate("openmenu", "Spider-Man (USA)", 100, local_path=str(first))], "spider-man")
    monkeypatch.setattr(
        "openmenu_gdemu_manager.covers.providers.registry.local_candidates",
        lambda *args, **kwargs: [Candidate("local", "Spider-Man (Europe)", 96, local_path=str(second))],
    )

    candidates = find_candidates(game, "spider-man", enabled_provider_ids=["local"], manual_mode=True)
    saved = load_saved_candidates(game)

    assert {candidate.title for candidate in candidates} == {"Spider-Man (USA)", "Spider-Man (Europe)"}
    assert {candidate.title for candidate in saved} == {"Spider-Man (USA)", "Spider-Man (Europe)"}
    assert count_new_candidates([candidate for candidate in saved if candidate.title.endswith("(USA)")], saved) == 1


def test_replacing_cover_preserves_previous_cover_in_library(tmp_path, monkeypatch):
    monkeypatch.setattr("openmenu_gdemu_manager.services.cover_library.COVER_LIBRARY_DIR", tmp_path / "library")
    monkeypatch.setattr("openmenu_gdemu_manager.services.cover_service.INBOX_ORIGINALS_DIR", tmp_path / "inbox" / "originals")
    monkeypatch.setattr("openmenu_gdemu_manager.services.cover_service.INBOX_NORMALIZED_DIR", tmp_path / "inbox" / "normalized")
    monkeypatch.setattr("openmenu_gdemu_manager.services.cover_service.INBOX_PREVIEW_DIR", tmp_path / "inbox" / "preview")
    previous = _image(tmp_path / "current" / "old.png", (20, 200, 20))
    new_image = Image.new("RGB", (512, 512), (20, 20, 200))
    game = GameItem(slot=2, name="18 Wheeler", product_id="MK51064", current_cover=previous)
    candidate = Candidate("openmenu", "18 Wheeler - American Pro Trucker (USA)", 100)

    persist_cover_selection(
        game,
        candidate,
        new_image,
        analyze_image(new_image),
        "seleccionada",
        state_path=tmp_path / "state.json",
        state={},
        root_path=tmp_path,
        persist_state=False,
    )

    saved = load_saved_candidates(game)
    assert {candidate.source for candidate in saved} == {"current_cover", "openmenu"}
    assert all(Path(candidate.cached_path).exists() for candidate in saved)
