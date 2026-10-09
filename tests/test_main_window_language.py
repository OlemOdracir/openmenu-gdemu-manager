import json
from string import Formatter

import pytest
from PySide6.QtWidgets import QApplication

from openmenu_gdemu_manager.i18n import active_language, load_internal_language, refresh_languages, registry, set_language
from openmenu_gdemu_manager.ui import main_window


@pytest.fixture
def window(monkeypatch, tmp_path):
    app = QApplication.instance() or QApplication([])
    previous = active_language()
    previous_language_dir = registry().languages_dir
    settings = {"ui": {"language": "en", "show_button_labels": True, "show_status_column": True}}
    monkeypatch.setattr(main_window, "migrate_legacy_runtime_data", lambda: None)
    monkeypatch.setattr(main_window, "load_settings", lambda: settings)
    monkeypatch.setattr(main_window, "load_state", lambda path: {})
    monkeypatch.setattr(main_window, "configured_languages_dir", lambda _: tmp_path)
    monkeypatch.setattr(main_window, "configured_template_dir", lambda _: tmp_path)
    monkeypatch.setattr(
        main_window, "set_ui_preference",
        lambda key, value, current: {**current, "ui": {**current["ui"], key: value}},
    )
    view = main_window.MainWindow()
    yield view
    view.close()
    view.deleteLater()
    app.processEvents()
    refresh_languages(previous_language_dir)
    set_language(previous)


def test_language_switch_updates_existing_buttons_and_preserves_filter(window):
    window.status_filter.setCurrentIndex(window.status_filter.findData("faltante"))
    for code, texts in (
        ("es", ("Seleccionar ruta SD/respaldo", "Escanear ruta seleccionada", "Agregar juego a la SD")),
        ("en", ("Select SD/backup path", "Scan selected path", "Add game to SD")),
    ):
        window.change_language(code)
        for button, expected in zip((window.browse_button, window.scan_button, window.add_game_button), texts):
            assert button.toolTip() == expected
            assert button.accessibleName() == expected
        assert window.browse_button.text() == ("Ruta" if code == "es" else "Path")
        assert window.templates_menu.title() == ("Plantillas" if code == "es" else "Templates")
        assert window.status_filter.currentData() == "faltante"
        assert window.save_changes_button.accessibleName() == window.save_changes_button.toolTip()


def test_reloading_language_updates_existing_toolbar(window):
    language_dir = main_window.configured_languages_dir(window.settings)
    package = {"language_code": "es", "strings": {"toolbar.path_tooltip": "Seleccionar tarjeta de prueba"}}
    (language_dir / "es.json").write_text(json.dumps(package), encoding="utf-8")
    window.settings["ui"]["language"] = "es"
    window.reload_languages()
    assert window.browse_button.toolTip() == "Seleccionar tarjeta de prueba"
    assert window.browse_button.accessibleName() == "Seleccionar tarjeta de prueba"


def test_spanish_catalog_has_all_keys_and_matching_format_fields():
    en = load_internal_language("en").strings
    es = load_internal_language("es").strings
    assert en.keys() == es.keys()
    formatter = Formatter()
    for key, value in en.items():
        fields = lambda text: sorted(field for _, field, _, _ in formatter.parse(text) if field is not None)
        assert fields(value) == fields(es[key]), key

