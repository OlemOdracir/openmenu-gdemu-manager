from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QDialog, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..icons import vendor_qicon


class ConfirmApplyDialog(QDialog):
    def __init__(self, root_path: Path, covers: int, additions: int, deletions: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Aplicar cambios en SD")
        self.setModal(True)
        self.resize(620, 360)
        self.root_path = Path(root_path)
        self.covers = covers
        self.additions = additions
        self.deletions = deletions
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        hero = QWidget()
        hero.setObjectName("SecurityCard")
        hero_row = QHBoxLayout(hero)
        hero_row.setContentsMargins(18, 16, 18, 16)
        icon = QLabel()
        icon.setFixedSize(58, 58)
        icon.setPixmap(vendor_qicon("tabler", "device-sd-card", "warning", 54).pixmap(QSize(54, 54)))
        icon.setStyleSheet("background: transparent;")
        hero_row.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)
        text = QVBoxLayout()
        title = QLabel("Aplicar cambios reales en la SD")
        title.setObjectName("StatusTitle")
        message = QLabel(
            f"Se escribira en <b>{self.root_path}</b>. La app copiara juegos pendientes, "
            "actualizara OpenMenu y guardara las caratulas propuestas."
        )
        message.setObjectName("StatusMessage")
        message.setTextFormat(Qt.TextFormat.RichText)
        message.setWordWrap(True)
        text.addWidget(title)
        text.addWidget(message)
        hero_row.addLayout(text, 1)
        layout.addWidget(hero)

        grid = QGridLayout()
        grid.setSpacing(10)
        grid.addWidget(self._metric_card("Caratulas", self.covers, "photo", "success"), 0, 0)
        grid.addWidget(self._metric_card("Juegos a copiar", self.additions, "plus", "accent"), 0, 1)
        grid.addWidget(self._metric_card("Juegos a eliminar", self.deletions, "trash", "danger"), 0, 2)
        layout.addLayout(grid)

        note = QLabel("Esta accion no formatea la SD, pero si modifica archivos OpenMenu y slots de juegos.")
        note.setObjectName("ChipWarning")
        note.setWordWrap(True)
        layout.addWidget(note)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = _dialog_button("Cancelar", "x", "default")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        apply = _dialog_button("Aplicar en SD", "circle-check", "success")
        apply.clicked.connect(self.accept)
        buttons.addWidget(apply)
        layout.addLayout(buttons)

    def _metric_card(self, title: str, value: int, icon_name: str, variant: str) -> QWidget:
        card = QWidget()
        card.setObjectName("DiagnosticTile")
        row = QHBoxLayout(card)
        row.setContentsMargins(14, 12, 14, 12)
        icon = QLabel()
        icon.setFixedSize(34, 34)
        icon.setPixmap(vendor_qicon("tabler", icon_name, variant, 32).pixmap(QSize(32, 32)))
        icon.setStyleSheet("background: transparent;")
        row.addWidget(icon)
        col = QVBoxLayout()
        label = QLabel(title)
        label.setObjectName("TileTitle")
        count = QLabel(str(value))
        count.setObjectName("WizardTitle")
        col.addWidget(label)
        col.addWidget(count)
        row.addLayout(col, 1)
        return card


def _dialog_button(text: str, icon_name: str, variant: str) -> QPushButton:
    button = QPushButton(text)
    button.setIcon(vendor_qicon("tabler", icon_name, variant, 22))
    button.setIconSize(QSize(22, 22))
    button.setMinimumHeight(44)
    button.setMinimumWidth(150)
    button.setProperty("variant", variant)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button
