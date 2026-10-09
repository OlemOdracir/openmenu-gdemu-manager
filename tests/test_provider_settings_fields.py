"""Provider form localization preserves the original configuration controls."""

import pytest
from PySide6.QtWidgets import QApplication, QCheckBox, QFormLayout, QLineEdit, QSpinBox

from openmenu_gdemu_manager.i18n import active_language, load_internal_language, set_language
from openmenu_gdemu_manager.ui.dialogs.provider_settings import ProviderConfigDialog


@pytest.fixture
def localized_app():
    app = QApplication.instance() or QApplication([])
    previous = active_language()
    yield app
    set_language(previous)


@pytest.mark.parametrize("language", ["en", "es"])
@pytest.mark.parametrize("provider", ["screenscraper", "igdb"])
def test_provider_form_localizes_labels_and_preserves_controls(localized_app, language, provider):
    set_language(language)
    definitions = ProviderConfigDialog.FIELD_MAP.get(provider, ProviderConfigDialog.FIELD_MAP["default"])
    cfg = {key: True if kind == "bool" else 75 if kind == "int" else "sample-secret" for key, _, kind in definitions}
    dialog = ProviderConfigDialog(provider, "Source", {"cover_providers": {provider: cfg}})
    try:
        form = dialog.findChild(QFormLayout)
        catalog = load_internal_language(language).strings
        assert form.rowCount() == len(definitions)
        for row, (key, label_key, kind) in enumerate(definitions):
            assert label_key.startswith("dialog.provider.field.")
            assert form.itemAt(row, QFormLayout.ItemRole.LabelRole).widget().text() == catalog[label_key]
            widget = dialog.inputs[key]
            assert form.itemAt(row, QFormLayout.ItemRole.FieldRole).widget() is widget
            if kind == "bool":
                assert isinstance(widget, QCheckBox)
                assert widget.isChecked()
            elif kind == "int":
                assert isinstance(widget, QSpinBox)
                assert (widget.minimum(), widget.maximum(), widget.value()) == (0, 999, 75)
            else:
                assert isinstance(widget, QLineEdit)
                expected_mode = QLineEdit.EchoMode.Password if kind == "password" else QLineEdit.EchoMode.Normal
                assert widget.echoMode() == expected_mode
                assert widget.text() == "sample-secret"
        dialog.accept()
        assert dialog.values() == cfg
    finally:
        dialog.deleteLater()
        localized_app.processEvents()


def test_provider_form_keeps_missing_optional_fields_hidden(localized_app):
    dialog = ProviderConfigDialog("screenscraper", "Source", {"cover_providers": {"screenscraper": {"enabled": False}}})
    try:
        assert set(dialog.inputs) == {"enabled"}
        assert dialog.findChild(QFormLayout).rowCount() == 1
    finally:
        dialog.deleteLater()
        localized_app.processEvents()


def test_provider_field_catalogs_have_distinct_translated_labels():
    en = load_internal_language("en").strings
    es = load_internal_language("es").strings
    assert en["dialog.provider.field.enabled"] == "Active"
    assert es["dialog.provider.field.enabled"] == "Activo"
    assert en["dialog.provider.field.min_auto_score"] == "Automatic selection threshold"
    assert es["dialog.provider.field.min_auto_score"] == "Umbral de selección automática"
