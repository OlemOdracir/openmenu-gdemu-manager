from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ...core.models import Candidate, GameItem
from ...config.settings import cover_provider_settings
from .libretro import libretro_candidates
from .local import local_candidates
from .openmenu import openmenu_candidates


FindCallback = Callable[[GameItem, str, dict[str, Any]], list[Candidate]]
TestCallback = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class ProviderDefinition:
    id: str
    label: str
    requires_credentials: bool = False
    signup_url: str = ""
    find: FindCallback | None = None
    test: TestCallback | None = None
    remote: bool = True


def _local_find(game: GameItem, query: str, settings: dict[str, Any]) -> list[Candidate]:
    return local_candidates(game, query, settings)


def _openmenu_find(game: GameItem, query: str, settings: dict[str, Any]) -> list[Candidate]:
    return openmenu_candidates(game, query)


def _libretro_find(game: GameItem, query: str, settings: dict[str, Any]) -> list[Candidate]:
    return libretro_candidates(game, query)


def _local_test(settings: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True, "message": "Provider local disponible.", "count": 0}


def _remote_test(label: str) -> TestCallback:
    def _test(settings: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True, "message": f"{label} configurado. La prueba real se ejecuta durante busqueda.", "count": 0}
    return _test


def _not_implemented(label: str) -> TestCallback:
    def _test(settings: dict[str, Any]) -> dict[str, Any]:
        return {"ok": False, "message": f"{label} esta reservado, pero aun no implementado.", "count": 0}
    return _test


def _definitions() -> dict[str, ProviderDefinition]:
    from .screenscraper import screenscraper_candidates, test_connection as test_screenscraper

    return {
        "local": ProviderDefinition("local", "Carpetas locales", False, "", _local_find, _local_test, remote=False),
        "openmenu": ProviderDefinition("openmenu", "openMenu image DB", False, "https://github.com/mrneo240/openMenu_imagedb", _openmenu_find, _remote_test("openMenu")),
        "libretro": ProviderDefinition("libretro", "Libretro thumbnails", False, "https://github.com/libretro-thumbnails/Sega_-_Dreamcast", _libretro_find, _remote_test("Libretro")),
        "screenscraper": ProviderDefinition("screenscraper", "ScreenScraper", True, "https://www.screenscraper.fr/", screenscraper_candidates, test_screenscraper),
        "mobygames": ProviderDefinition("mobygames", "MobyGames", True, "https://www.mobygames.com/api/subscribe/", None, _not_implemented("MobyGames")),
        "igdb": ProviderDefinition("igdb", "IGDB", True, "https://api-docs.igdb.com/#getting-started", None, _not_implemented("IGDB")),
        "rawg": ProviderDefinition("rawg", "RAWG", True, "https://rawg.io/apidocs", None, _not_implemented("RAWG")),
        "brave_image": ProviderDefinition("brave_image", "Brave Image Search", True, "https://brave.com/search/api/", None, _not_implemented("Brave Image Search")),
        "google_image": ProviderDefinition("google_image", "Google Custom Search", True, "https://developers.google.com/custom-search/v1/overview", None, _not_implemented("Google Custom Search")),
    }


def provider_definitions() -> dict[str, ProviderDefinition]:
    return _definitions()


def source_provider_id(source: str) -> str:
    return (source or "").split("/", 1)[0].strip().lower()


def provider_config(settings: dict[str, Any], provider_id: str) -> dict[str, Any]:
    return cover_provider_settings(settings).get(provider_id, {})


def provider_threshold(settings: dict[str, Any], provider_id: str, key: str, default: int) -> int:
    try:
        return int(provider_config(settings, provider_id).get(key, default) or default)
    except Exception:
        return default


def is_provider_enabled(settings: dict[str, Any], provider_id: str) -> bool:
    providers = cover_provider_settings(settings)
    if provider_id in providers:
        return bool(providers[provider_id].get("enabled", False))
    return bool(settings.get("providers", {}).get(provider_id, False))


def iter_enabled_providers(
    settings: dict[str, Any],
    include_remote: bool = True,
    enabled_provider_ids: list[str] | set[str] | tuple[str, ...] | None = None,
) -> list[ProviderDefinition]:
    wanted = {item.lower() for item in enabled_provider_ids} if enabled_provider_ids else None
    definitions = provider_definitions()
    rows: list[tuple[int, ProviderDefinition]] = []
    for provider_id, definition in definitions.items():
        if wanted is not None and provider_id not in wanted:
            continue
        if definition.remote and not include_remote:
            continue
        if wanted is None and not is_provider_enabled(settings, provider_id):
            continue
        if definition.find is None:
            continue
        cfg = provider_config(settings, provider_id)
        rows.append((int(cfg.get("priority", 999) or 999), definition))
    return [definition for _, definition in sorted(rows, key=lambda item: (item[0], item[1].id))]


def test_provider(provider_id: str, settings: dict[str, Any]) -> dict[str, Any]:
    definition = provider_definitions().get(provider_id)
    if definition is None:
        return {"ok": False, "message": f"Provider desconocido: {provider_id}", "count": 0}
    if definition.test is None:
        return {"ok": False, "message": f"{definition.label} no tiene prueba implementada.", "count": 0}
    return definition.test(settings)
