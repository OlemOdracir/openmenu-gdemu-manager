import json
import os
from pathlib import Path
from typing import Any

from .paths import (
    BASE_DIR,
    BUNDLED_BUILDGDI_PATH,
    BUNDLED_OPENMENU_TOOLS_DIR,
    INBOX_NORMALIZED_DIR,
    INBOX_ORIGINALS_DIR,
    LANGUAGES_DIR,
    LOCAL_IMAGE_DIRS,
    SETTINGS_PATH,
    UI_TEMPLATES_DIR,
)


DEFAULT_SETTINGS: dict[str, Any] = {
    "version": 1,
    "providers": {
        "local": True,
        "openmenu": True,
        "libretro": True,
    },
    "cover_providers": {
        "local": {
            "enabled": True,
            "priority": 10,
            "min_auto_score": 82,
            "min_review_score": 65,
        },
        "openmenu": {
            "enabled": True,
            "priority": 20,
            "min_auto_score": 86,
            "min_review_score": 65,
        },
        "libretro": {
            "enabled": True,
            "priority": 30,
            "min_auto_score": 86,
            "min_review_score": 65,
        },
        "community_api": {
            "enabled": True,
            "base_url": "https://openmenu-gdemu-cover-api.openmenu-gdemu-manager.workers.dev",
            "timeout": 20,
            "priority": 35,
            "min_auto_score": 86,
            "min_review_score": 65,
        },
        "screenscraper": {
            "enabled": False,
            "base_url": "https://api.screenscraper.fr/api2",
            "signup_url": "https://www.screenscraper.fr/",
            "devid": "",
            "devpassword": "",
            "softname": "OpenMenuGDEMUManager",
            "ssid": "",
            "sspassword": "",
            "systemeid": 23,
            "timeout": 30,
            "priority": 40,
            "min_auto_score": 90,
            "min_review_score": 70,
        },
        "mobygames": {
            "enabled": False,
            "base_url": "https://api.mobygames.com/v1",
            "signup_url": "https://www.mobygames.com/api/subscribe/",
            "api_key": "",
            "priority": 60,
            "min_auto_score": 90,
            "min_review_score": 70,
        },
        "igdb": {
            "enabled": False,
            "base_url": "https://api.igdb.com/v4",
            "signup_url": "https://api-docs.igdb.com/#getting-started",
            "client_id": "",
            "client_secret": "",
            "priority": 70,
            "min_auto_score": 90,
            "min_review_score": 70,
        },
        "rawg": {
            "enabled": False,
            "base_url": "https://api.rawg.io/api",
            "signup_url": "https://rawg.io/apidocs",
            "api_key": "",
            "priority": 80,
            "min_auto_score": 92,
            "min_review_score": 72,
        },
        "brave_image": {
            "enabled": False,
            "base_url": "https://api.search.brave.com/res/v1/images/search",
            "signup_url": "https://brave.com/search/api/",
            "api_key": "",
            "priority": 90,
            "min_auto_score": 95,
            "min_review_score": 78,
        },
        "google_image": {
            "enabled": False,
            "base_url": "https://www.googleapis.com/customsearch/v1",
            "signup_url": "https://developers.google.com/custom-search/v1/overview",
            "api_key": "",
            "cx": "",
            "priority": 100,
            "min_auto_score": 95,
            "min_review_score": 78,
        },
    },
    "allow_remote_downloads": True,
    "candidate_limit": 60,
    "visible_candidate_limit": 18,
    "dedupe_preload_limit": 90,
    "local_image_dirs": [
        str(path.relative_to(BASE_DIR))
        for path in [
            *LOCAL_IMAGE_DIRS,
            BASE_DIR / "_cover_manager_cache" / "downloads",
            BASE_DIR / "_cover_inbox" / "originals",
            BASE_DIR / "_cover_inbox" / "normalized",
        ]
    ],
    "rom_library_dirs": [
        "Juegos",
        "Ntsc",
        "PAL",
        "ROM favoritos",
    ],
    "supported_media_types": ["GDI", "CDI"],
    "default_import_mode": "copy",
    "openmenu_setup": {
        "template_dir": "_OpenMenuBuild",
        "buildgdi_path": str(BUNDLED_BUILDGDI_PATH),
        "buildgdi_expected_version": "BuildGDI v2.1.1",
        "buildgdi_expected_sha256": "52C0B7388DEFF46652F35F3F26AC8D2E6B29720E06BD7EDE450DAA0DFF0A8C5E",
        "menu_gdi_dir": str(BUNDLED_OPENMENU_TOOLS_DIR / "menu_gdi"),
        "menu_data_dir": str(BUNDLED_OPENMENU_TOOLS_DIR / "menu_data"),
        "menu_source_mode": "current_sd",
    },
    "web_search_templates": [
        {
            "name": "Google Images",
            "url": "https://www.google.com/search?tbm=isch&q={query}",
        },
        {
            "name": "DuckDuckGo Images",
            "url": "https://duckduckgo.com/?q={query}&iax=images&ia=images",
        },
        {
            "name": "Bing Images",
            "url": "https://www.bing.com/images/search?q={query}",
        },
        {
            "name": "The Cover Project",
            "url": "https://www.google.com/search?tbm=isch&q=site:thecoverproject.net+{query}",
        },
        {
            "name": "Product ID",
            "url": "https://www.google.com/search?tbm=isch&q={product_id}+Dreamcast+cover",
        },
    ],
    "optional_api_providers": {
        "thegamesdb": {"enabled": False, "api_key": ""},
        "igdb": {"enabled": False, "client_id": "", "client_secret": ""},
        "mobygames": {"enabled": False, "api_key": ""},
    },
    "ui": {
        "active_template": "basic_formal",
        "template_dir": str(UI_TEMPLATES_DIR.relative_to(BASE_DIR)),
        "language": "en",
        "language_prompted": False,
        "languages_dir": str(LANGUAGES_DIR.relative_to(BASE_DIR)),
        "check_updates_on_startup": True,
        "last_update_check": "",
        "background_enabled": True,
        "music_enabled": False,
        "music_volume": 35,
        "backup_decisions": {},
        "icon_style": "themed",
        "animations": True,
        "show_button_labels": False,
        "show_status_column": False,
    },
}


def load_settings(path: Path = SETTINGS_PATH) -> dict[str, Any]:
    if not path.exists():
        save_settings(DEFAULT_SETTINGS, path)
        return json.loads(json.dumps(DEFAULT_SETTINGS))
    try:
        with path.open("r", encoding="utf-8") as handle:
            loaded = json.load(handle)
    except Exception:
        return json.loads(json.dumps(DEFAULT_SETTINGS))
    merged = merge_settings(DEFAULT_SETTINGS, loaded)
    if "cover_providers" not in loaded:
        for provider_id, enabled in loaded.get("providers", {}).items():
            if provider_id in merged.get("cover_providers", {}):
                merged["cover_providers"][provider_id]["enabled"] = bool(enabled)
    return merged


def save_settings(settings: dict[str, Any], path: Path = SETTINGS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(settings, handle, ensure_ascii=False, indent=2)


def merge_settings(defaults: dict[str, Any], loaded: dict[str, Any]) -> dict[str, Any]:
    merged = json.loads(json.dumps(defaults))
    for key, value in loaded.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_settings(merged[key], value)
        else:
            merged[key] = value
    return merged


def configured_local_dirs(settings: dict[str, Any]) -> list[Path]:
    result: list[Path] = []
    configured = list(settings.get("local_image_dirs") or [
        *LOCAL_IMAGE_DIRS,
        BASE_DIR / "_cover_manager_cache" / "downloads",
        INBOX_ORIGINALS_DIR,
        INBOX_NORMALIZED_DIR,
    ])
    for raw in configured:
        path = Path(str(raw))
        if not path.is_absolute():
            path = BASE_DIR / path
        if path not in result:
            result.append(path)
    return result


def web_search_templates(settings: dict[str, Any] | None = None) -> list[dict[str, str]]:
    settings = settings or load_settings()
    templates = settings.get("web_search_templates", [])
    return [template for template in templates if template.get("name") and template.get("url")]


def cover_provider_settings(settings: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    settings = settings or load_settings()
    return settings.get("cover_providers", {})


def set_cover_provider_settings(provider_id: str, provider_settings: dict[str, Any],
                                settings: dict[str, Any] | None = None,
                                path: Path = SETTINGS_PATH) -> dict[str, Any]:
    settings = settings or load_settings(path)
    settings.setdefault("cover_providers", {})
    settings["cover_providers"].setdefault(provider_id, {})
    settings["cover_providers"][provider_id].update(provider_settings)
    save_settings(settings, path)
    return settings


def configured_rom_dirs(settings: dict[str, Any]) -> list[Path]:
    result: list[Path] = []
    for raw in settings.get("rom_library_dirs", []):
        path = Path(str(raw))
        if not path.is_absolute():
            path = BASE_DIR / path
        if path not in result:
            result.append(path)
    return result


def supported_media_types(settings: dict[str, Any]) -> set[str]:
    return {str(value).upper() for value in settings.get("supported_media_types", ["GDI", "CDI"])}


def configured_openmenu_template_dir(settings: dict[str, Any] | None = None) -> Path:
    settings = settings or load_settings()
    raw = settings.get("openmenu_setup", {}).get("template_dir", "_OpenMenuBuild")
    path = Path(str(raw))
    if not path.is_absolute():
        path = BASE_DIR / path
    return path


def configured_buildgdi_path(settings: dict[str, Any] | None = None) -> Path:
    settings = settings or load_settings()
    if BUNDLED_BUILDGDI_PATH.exists():
        return BUNDLED_BUILDGDI_PATH
    raw = settings.get("openmenu_setup", {}).get("buildgdi_path", "")
    path = Path(str(raw))
    if not path.is_absolute():
        path = BASE_DIR / path
    return path


def configured_buildgdi_expected_version(settings: dict[str, Any] | None = None) -> str:
    settings = settings or load_settings()
    return str(settings.get("openmenu_setup", {}).get("buildgdi_expected_version", "") or "").strip()


def configured_buildgdi_expected_sha256(settings: dict[str, Any] | None = None) -> str:
    settings = settings or load_settings()
    return str(settings.get("openmenu_setup", {}).get("buildgdi_expected_sha256", "") or "").strip().upper()


def configured_menu_gdi_dir(settings: dict[str, Any] | None = None) -> Path:
    settings = settings or load_settings()
    bundled = BUNDLED_OPENMENU_TOOLS_DIR / "menu_gdi"
    if bundled.is_dir():
        return bundled
    raw = settings.get("openmenu_setup", {}).get("menu_gdi_dir", "")
    path = Path(str(raw))
    if not path.is_absolute():
        path = BASE_DIR / path
    return path


def configured_menu_data_dir(settings: dict[str, Any] | None = None) -> Path:
    settings = settings or load_settings()
    bundled = BUNDLED_OPENMENU_TOOLS_DIR / "menu_data"
    if bundled.is_dir():
        return bundled
    raw = settings.get("openmenu_setup", {}).get("menu_data_dir", "")
    path = Path(str(raw))
    if not path.is_absolute():
        path = BASE_DIR / path
    return path


def ui_settings(settings: dict[str, Any] | None = None) -> dict[str, Any]:
    settings = settings or load_settings()
    return settings.get("ui", {})


def active_template(settings: dict[str, Any] | None = None) -> str:
    ui = ui_settings(settings)
    template = str(ui.get("active_template", "basic_formal") or "basic_formal").strip()
    if not template:
        return "basic_formal"
    return template


def set_active_template(settings: dict[str, Any], template_name: str, path: Path = SETTINGS_PATH) -> dict[str, Any]:
    normalized = str(template_name or "").strip()
    if not normalized:
        normalized = "basic_formal"
    settings.setdefault("ui", {})
    settings["ui"]["active_template"] = normalized
    save_settings(settings, path)
    return settings


def configured_template_dir(settings: dict[str, Any] | None = None) -> Path:
    ui = ui_settings(settings)
    raw = ui.get("template_dir", "_ui_templates")
    path = Path(str(raw))
    if not path.is_absolute():
        path = BASE_DIR / path
    return path


def set_ui_preference(key: str, value: Any, settings: dict[str, Any] | None = None,
                      path: Path = SETTINGS_PATH) -> dict[str, Any]:
    settings = settings or load_settings(path)
    settings.setdefault("ui", {})
    settings["ui"][key] = value
    save_settings(settings, path)
    return settings


def configured_languages_dir(settings: dict[str, Any] | None = None) -> Path:
    ui = ui_settings(settings)
    raw = ui.get("languages_dir", "languages")
    path = Path(str(raw))
    if not path.is_absolute():
        path = BASE_DIR / path
    return path
