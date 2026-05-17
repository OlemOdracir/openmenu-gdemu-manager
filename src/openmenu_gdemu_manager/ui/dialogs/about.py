from __future__ import annotations

from importlib import metadata

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from ... import APP_NAME, CONTACT_URL, REPOSITORY_URL, __version__
from ...config.paths import BASE_DIR
from ...i18n import tr
from ..icons import app_logo_pixmap


def app_version() -> str:
    try:
        return metadata.version("openmenu-gdemu-manager")
    except metadata.PackageNotFoundError:
        return __version__


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("dialog.about.title"))
        self.resize(560, 360)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)

        header = QHBoxLayout()
        logo = QLabel()
        logo.setFixedSize(64, 64)
        logo.setPixmap(app_logo_pixmap(62))
        header.addWidget(logo)

        title = QLabel(APP_NAME)
        title.setObjectName("WizardTitle")
        header.addWidget(title, 1)
        layout.addLayout(header)

        body = QLabel(tr(
            "dialog.about.body",
            app=APP_NAME,
            version=app_version(),
            repo=REPOSITORY_URL,
            contact=CONTACT_URL,
            data_dir=BASE_DIR,
        ))
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(body, 1)

        close = QPushButton(tr("action.close"))
        close.clicked.connect(self.accept)
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(close, 0, Qt.AlignmentFlag.AlignRight)
