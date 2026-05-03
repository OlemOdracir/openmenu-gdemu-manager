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
