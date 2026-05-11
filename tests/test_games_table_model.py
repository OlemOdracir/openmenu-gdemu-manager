import pytest

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

from openmenu_gdemu_manager.core.models import GameItem
from openmenu_gdemu_manager.ui.widgets.games_table_model import GamesTableModel


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_missing_cover_uses_default_placeholder(qapp):
    model = GamesTableModel()
    model.set_games([GameItem(slot=105, name="METAL SLUG 2", status="faltante")])

    pixmap = model.data(model.index(0, GamesTableModel.C_COVER), Qt.ItemDataRole.UserRole)

    assert isinstance(pixmap, QPixmap)
    assert not pixmap.isNull()


def test_bulk_header_reflects_selection_state(qapp):
    model = GamesTableModel()
    model.set_games([GameItem(slot=2, name="A"), GameItem(slot=3, name="B")])

    model.set_bulk_mode(True, {2: False, 3: False})
    assert model.headerData(GamesTableModel.C_CHECK, Qt.Orientation.Horizontal) == ""
    assert model.bulk_header_check_state() == Qt.CheckState.Unchecked

    model.set_bulk_mode(True, {2: True, 3: False})
    assert model.headerData(GamesTableModel.C_CHECK, Qt.Orientation.Horizontal) == ""
    assert model.bulk_header_check_state() == Qt.CheckState.PartiallyChecked

    model.set_bulk_mode(True, {2: True, 3: True})
    assert model.headerData(GamesTableModel.C_CHECK, Qt.Orientation.Horizontal) == ""
    assert model.bulk_header_check_state() == Qt.CheckState.Checked
