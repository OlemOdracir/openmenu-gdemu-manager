from openmenu_gdemu_manager.ui.workers import _latest_release_from_payload, _version_key


def test_latest_release_includes_prereleases():
    payload = [
        {"tag_name": "v0.2.0-beta.1", "html_url": "https://example.test/1"},
        {"tag_name": "v0.2.0-beta.3", "html_url": "https://example.test/3"},
        {"tag_name": "v0.1.9", "html_url": "https://example.test/old"},
    ]

    latest = _latest_release_from_payload(payload)

    assert latest is not None
    assert latest["tag_name"] == "v0.2.0-beta.3"


def test_latest_release_ignores_drafts():
    payload = [
        {"tag_name": "v0.2.0-beta.4", "draft": True},
        {"tag_name": "v0.2.0-beta.3", "draft": False},
    ]

    latest = _latest_release_from_payload(payload)

    assert latest is not None
    assert latest["tag_name"] == "v0.2.0-beta.3"


def test_stable_release_sorts_after_prerelease_with_same_base_version():
    assert _version_key("0.2.0") > _version_key("0.2.0-beta.99")


def test_two_digit_beta_version_sorts_correctly():
    assert _version_key("0.2.0-beta.10") > _version_key("0.2.0-beta.3")
