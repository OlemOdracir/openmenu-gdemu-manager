from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QDialog, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ...i18n import tr
from ..icons import vendor_qicon


class ConfirmApplyDialog(QDialog):
    def __init__(
        self,
        root_path: Path,
        covers: int,
        additions: int,
        deletions: int,
        parent=None,
        *,
        slot_moves: int = 0,
        product_updates: int = 0,
    ):
        super().__init__(parent)
        self.setWindowTitle(tr("dialog.confirm_apply.title"))
        self.setModal(True)
        self.resize(760, 430)
        self.root_path = Path(root_path)
        self.covers = covers
        self.additions = additions
        self.deletions = deletions
        self.slot_moves = slot_moves
        self.product_updates = product_updates
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
        title = QLabel(self._title_text())
        title.setObjectName("StatusTitle")
        message = QLabel(self._message_text())
        message.setObjectName("StatusMessage")
        message.setTextFormat(Qt.TextFormat.RichText)
        message.setWordWrap(True)
        text.addWidget(title)
        text.addWidget(message)
        hero_row.addLayout(text, 1)
        layout.addWidget(hero)

        grid = QGridLayout()
        grid.setSpacing(10)
        grid.addWidget(self._metric_card(tr("dialog.confirm_apply.covers"), self.covers, "photo", "success"), 0, 0)
        grid.addWidget(self._metric_card(tr("dialog.confirm_apply.additions"), self.additions, "plus", "accent"), 0, 1)
        grid.addWidget(self._metric_card(tr("dialog.confirm_apply.deletions"), self.deletions, "trash", "danger"), 0, 2)
        grid.addWidget(self._metric_card(tr("dialog.confirm_apply.slot_moves"), self.slot_moves, "arrows-shuffle", "warning"), 1, 0)
        grid.addWidget(self._metric_card(tr("dialog.confirm_apply.product_updates"), self.product_updates, "id", "accent"), 1, 1)
        layout.addLayout(grid)

        note = QLabel(self._note_text())
        note.setObjectName("ChipWarning" if self._is_large_operation() else "ChipInfo")
        note.setWordWrap(True)
        layout.addWidget(note)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = _dialog_button(tr("action.cancel"), "x", "default")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        apply = _dialog_button(self._apply_button_text(), "circle-check", "success")
        apply.clicked.connect(self.accept)
        buttons.addWidget(apply)
        layout.addLayout(buttons)

    def _title_text(self) -> str:
        if self.slot_moves or self.product_updates:
            return tr("dialog.confirm_apply.repair_title")
        if self.covers and not self.additions and not self.deletions:
            return tr("dialog.confirm_apply.covers_title")
        return tr("dialog.confirm_apply.apply_title")

    def _message_text(self) -> str:
        root = f"<b>{self.root_path}</b>"
        actions: list[str] = [tr("dialog.confirm_apply.action_rebuild")]
        if self.slot_moves:
            actions.append(tr("dialog.confirm_apply.action_compact", count=self.slot_moves))
        if self.product_updates:
            actions.append(tr("dialog.confirm_apply.action_product", count=self.product_updates))
        if self.covers:
            actions.append(tr("dialog.confirm_apply.action_covers", count=self.covers))
        if self.additions:
            actions.append(tr("dialog.confirm_apply.action_add", count=self.additions))
        if self.deletions:
            actions.append(tr("dialog.confirm_apply.action_delete", count=self.deletions))
        return tr("dialog.confirm_apply.message", root=root, actions=", ".join(actions))

    def _note_text(self) -> str:
        if self._is_large_operation():
            return (
                tr("dialog.confirm_apply.large_note")
            )
        if self.slot_moves or self.deletions or self.additions:
            return tr("dialog.confirm_apply.slot_note")
        return tr("dialog.confirm_apply.cover_note")

    def _apply_button_text(self) -> str:
        if self.slot_moves or self.product_updates:
            return tr("dialog.confirm_apply.repair_button")
        if self.covers and not self.additions and not self.deletions:
            return tr("dialog.confirm_apply.covers_button")
        return tr("dialog.confirm_apply.apply_button")

    def _is_large_operation(self) -> bool:
        return self.slot_moves > 10 or self.deletions > 5

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
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        count = QLabel(str(value))
        count.setObjectName("WizardTitle")
        count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        col.addWidget(label)
        col.addWidget(count, 1)
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
