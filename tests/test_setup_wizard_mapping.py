from pathlib import Path

import pytest

from openmenu_gdemu_manager.dreamcast.storage_diagnostics import RouteSummary, StorageDiagnostic
from openmenu_gdemu_manager.i18n import active_language, set_language
from openmenu_gdemu_manager.ui.dialogs.setup_wizard import (
    _backup_recommended,
    _diagnostic_message,
    _diagnostic_tiles,
    _drive_type_label,
    _format_detail_lines,
    _health_label,
    _has_user_backup_content,
    _menu_label,
    _route_class_label,
)
from openmenu_gdemu_manager.ui.theme import build_stylesheet


@pytest.fixture(autouse=True)
def _spanish_language():
    previous = active_language()
    set_language("es")
    yield
    set_language(previous)


def _diagnostic(
    route="dangerous_path",
    health="ok",
    menu="unknown",
    write=False,
    scan=False,
    other=0,
    numeric=0,
    drive_type="removable",
    filesystem="FAT32",
    is_root=True,
):
    summary = RouteSummary(Path("H:/"), True, is_root, drive_type, filesystem)
    summary.other_entries = [str(index) for index in range(other)]
    summary.numeric_dirs = [f"{index:02d}" for index in range(1, numeric + 1)]
    return StorageDiagnostic(Path("H:/"), route, health, menu, write, scan, reason="mock", summary=summary)


def test_diagnostic_tiles_mark_dirty_sd_as_danger():
    tiles = {tile["id"]: tile for tile in _diagnostic_tiles(_diagnostic(other=8))}

    assert tiles["content"]["severity"] == "danger"
    assert tiles["content"]["value"] == "Archivos encontrados: 8"
    assert tiles["structure"]["severity"] == "danger"


def test_diagnostic_tiles_mark_openmenu_as_success():
    tiles = {
        tile["id"]: tile
        for tile in _diagnostic_tiles(
            _diagnostic("gdemu_structure", "ok", "openmenu_compatible", True, True, numeric=10)
        )
    }

    assert tiles["unit"]["severity"] == "success"
    assert tiles["filesystem"]["severity"] == "success"
    assert tiles["structure"]["severity"] == "success"
    assert tiles["content"]["severity"] == "success"


def test_diagnostic_tiles_do_not_warn_for_ntfs_local_folder():
    tiles = {
        tile["id"]: tile
        for tile in _diagnostic_tiles(
            _diagnostic(health="local_folder", drive_type="fixed", filesystem="NTFS", is_root=False, other=3)
        )
    }

    assert tiles["filesystem"]["severity"] == "success"
    assert tiles["filesystem"]["value"] == "No aplica en carpeta local"


def test_diagnostic_labels_are_human_readable():
    assert _route_class_label("dangerous_path") == "Ruta bloqueada"
    assert _health_label("ok") == "Correcta"
    assert _menu_label("unknown") == "No detectado"
    assert _drive_type_label("removable") == "Unidad extraíble"


def test_details_format_uses_bold_labels_and_code_values():
    html = _format_detail_lines([("Ruta", "H:/", True), ("Menu", "No detectado", False)])

    assert "<b>Ruta:</b>" in html
    assert "font-family: Consolas" in html
    assert "<b>Menu:</b> No detectado" in html


def test_setup_wizard_diagnostic_message_translates_storage_reason_to_english():
    set_language("en")
    diagnostic = StorageDiagnostic(
        Path("H:/"),
        "dangerous_path",
        "ok",
        "unknown",
        False,
        False,
        reason="La ruta no esta vacia y no tiene estructura GDEMU/OpenMenu.",
    )

    message = _diagnostic_message(diagnostic)

    assert "The path is not empty" in message
    assert "La ruta" not in message


def test_setup_wizard_diagnostic_message_keeps_spanish_when_language_is_spanish():
    diagnostic = StorageDiagnostic(
        Path("H:/"),
        "dangerous_path",
        "ok",
        "unknown",
        False,
        False,
        reason="La ruta no esta vacia y no tiene estructura GDEMU/OpenMenu.",
    )

    message = _diagnostic_message(diagnostic)

    assert "La ruta no" in message
    assert "no tiene estructura GDEMU/OpenMenu" in message


def test_backup_recommendation_ignores_openmenu_base_without_games():
    diagnostic = _diagnostic("gdemu_structure", "ok", "openmenu_compatible", True, True, numeric=1)

    assert _has_user_backup_content(diagnostic) is False
    assert _backup_recommended(diagnostic) is False


def test_backup_recommendation_detects_game_slots():
    diagnostic = _diagnostic("gdemu_structure", "ok", "openmenu_compatible", True, True, numeric=2)

    assert _has_user_backup_content(diagnostic) is True
    assert _backup_recommended(diagnostic) is True


def test_setup_wizard_security_icon_style_is_transparent():
    stylesheet = build_stylesheet("arcade_clean")

    assert "QLabel#SecurityIcon" in stylesheet
    assert "background: transparent;" in stylesheet
