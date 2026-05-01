import json

from openmenu_gdemu_manager.config.settings import DEFAULT_SETTINGS, load_settings, merge_settings


def test_old_settings_receive_cover_providers_defaults():
    merged = merge_settings(DEFAULT_SETTINGS, {"providers": {"local": False}})

    assert "cover_providers" in merged
    assert merged["cover_providers"]["community_api"]["enabled"] is True
    assert merged["cover_providers"]["screenscraper"]["enabled"] is False
    assert merged["cover_providers"]["local"]["enabled"] is True


def test_load_settings_maps_legacy_provider_flags(tmp_path):
    path = tmp_path / "cover_sources.json"
    path.write_text(json.dumps({"providers": {"local": False, "openmenu": True}}), encoding="utf-8")

    loaded = load_settings(path)

    assert loaded["cover_providers"]["local"]["enabled"] is False
    assert loaded["cover_providers"]["openmenu"]["enabled"] is True
