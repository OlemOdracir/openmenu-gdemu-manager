from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from ...i18n import LanguagePackage, tr
from ..icons import app_logo_pixmap


class LanguageSelectionDialog(QDialog):
    def __init__(self, languages: list[LanguagePackage], parent=None):
        super().__init__(parent)
        self.languages = sorted(languages, key=lambda item: (item.code != "en", item.label.lower()))
        self.selected_code = "en"
        self.setWindowTitle(tr("dialog.language.title"))
        self.setModal(True)
        self.resize(520, 260)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)

        header = QHBoxLayout()
        logo = QLabel()
        logo.setFixedSize(54, 54)
        logo.setPixmap(app_logo_pixmap(52))
        header.addWidget(logo)

        text = QVBoxLayout()
        title = QLabel(tr("dialog.language.heading"))
        title.setObjectName("WizardTitle")
        message = QLabel(tr("dialog.language.message"))
        message.setObjectName("WizardSubtitle")
        message.setWordWrap(True)
        text.addWidget(title)
        text.addWidget(message)
        header.addLayout(text, 1)
        layout.addLayout(header)

        self.combo = QComboBox()
        self.combo.setMinimumHeight(40)
        for language in self.languages:
            self.combo.addItem(language.label, language.code)
        english_index = max(0, self.combo.findData("en"))
        self.combo.setCurrentIndex(english_index)
        layout.addWidget(self.combo)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton(tr("action.cancel"))
        cancel.clicked.connect(self.reject)
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        buttons.addWidget(cancel)
        use = QPushButton(tr("dialog.language.use"))
        use.setProperty("variant", "success")
        use.clicked.connect(self.accept)
        use.setCursor(Qt.CursorShape.PointingHandCursor)
        buttons.addWidget(use)
        layout.addLayout(buttons)

    def accept(self):
        self.selected_code = str(self.combo.currentData() or "en")
        super().accept()
