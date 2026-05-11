from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...core.models import BulkProposal, GameItem
from ...i18n import tr, translate_status
from ..image_qt import file_to_pixmap, fit_pixmap, pil_to_pixmap
from ..icons import action_qicon
from ..widgets import apply_interactive_cursor, chip_label, region_to_flag


class CoverPreviewDialog(QDialog):
    def __init__(self, game: GameItem, proposal: BulkProposal | None = None, parent=None):
        super().__init__(parent)
        self.game = game
        self.proposal = proposal
        self.setWindowTitle(f"{game.slot:03d} - {game.name}")
        self.resize(760, 760)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel(self.game.name)
        title.setObjectName("WizardTitle")
        title.setWordWrap(True)
        subtitle = QLabel(tr("dialog.cover_preview.subtitle", slot=f"{self.game.slot:03d}", product=self.game.product_id or "-"))
        subtitle.setObjectName("WizardSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box, 1)
        header.addWidget(chip_label(tr("dialog.cover_preview.region", region=region_to_flag(self.game.region)), "accent"))
        if self.game.status:
            header.addWidget(chip_label(self._friendly_status(), self._status_chip_kind()))
        root.addLayout(header)

        image_card = QFrame()
        image_card.setObjectName("StatusCard")
        image_layout = QVBoxLayout(image_card)
        image_layout.setContentsMargins(18, 18, 18, 18)
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(520, 520)
        self.image_label.setObjectName("CandidatePreview")
        image_layout.addWidget(self.image_label, 1)
        root.addWidget(image_card, 1)

        details = QWidget()
        details.setObjectName("FilterBar")
        details_layout = QHBoxLayout(details)
        details_layout.setContentsMargins(14, 10, 14, 10)
        details_layout.setSpacing(16)
        for label, value in self._detail_items():
            item = QVBoxLayout()
            name = QLabel(label)
            name.setObjectName("MutedLabel")
            val = QLabel(str(value or "-"))
            val.setObjectName("TileTitle")
            val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            item.addWidget(name)
            item.addWidget(val)
            details_layout.addLayout(item)
        details_layout.addStretch(1)
        root.addWidget(details)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        close = QPushButton(tr("action.close"))
        close.setIcon(action_qicon("close", "default", 22))
        close.setIconSize(QSize(20, 20))
        close.setMinimumHeight(42)
        apply_interactive_cursor(close)
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        root.addLayout(buttons)

        self._load_image()

    def _load_image(self):
        pixmap = None
        if self.proposal and self.proposal.image is not None:
            try:
                pixmap = pil_to_pixmap(self.proposal.image, (680, 560))
            except Exception:
                pixmap = None
        if pixmap is None and self.game.current_cover and Path(self.game.current_cover).exists():
            try:
                pixmap = file_to_pixmap(self.game.current_cover, (680, 560))
            except Exception:
                pixmap = None
        if pixmap is None or pixmap.isNull():
            self.image_label.setText(tr("dialog.cover_preview.no_image"))
            return
        self.image_label.setPixmap(fit_pixmap(pixmap, 680, 560))

    def _detail_items(self) -> list[tuple[str, object]]:
        quality = self.game.quality_label or "-"
        score = self.game.quality_score or "-"
        source = self.game.selected_source or "-"
        image_size = "-"
        if self.game.image_width and self.game.image_height:
            image_size = f"{self.game.image_width}x{self.game.image_height}"
        if self.proposal and self.proposal.quality is not None:
            quality = getattr(self.proposal.quality, "label", quality)
            score = getattr(self.proposal.quality, "score", score)
            width = getattr(self.proposal.quality, "width", 0)
            height = getattr(self.proposal.quality, "height", 0)
            if width and height:
                image_size = f"{width}x{height}"
            if self.proposal.candidate is not None:
                source = self.proposal.candidate.source
        return [
            (tr("table.status"), self._friendly_status()),
            (tr("table.quality"), quality),
            (tr("dialog.cover_preview.score"), score),
            (tr("dialog.cover_preview.size"), image_size),
            (tr("dialog.cover_preview.source"), source),
        ]

    def _friendly_status(self) -> str:
        values = {
            "seleccionada": translate_status("seleccionada"),
            "correcta": translate_status("correcta"),
            "faltante": translate_status("faltante"),
            "no_revisada": translate_status("no_revisada"),
            "dudosa": translate_status("revision"),
        }
        if self.game.pending_add:
            return translate_status("pendiente_guardar")
        if self.game.pending_delete:
            return translate_status("pendiente_eliminar")
        if self.game.has_placeholder_cover:
            return translate_status("faltante")
        return values.get(self.game.status, self.game.status or "-")

    def _status_chip_kind(self) -> str:
        if self.game.pending_delete or self.game.status == "faltante" or self.game.has_placeholder_cover:
            return "warning"
        if self.game.status in {"seleccionada", "correcta"}:
            return "success"
        return "neutral"
