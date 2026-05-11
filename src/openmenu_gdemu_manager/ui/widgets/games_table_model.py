from __future__ import annotations

import logging
import traceback
from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QPushButton,
    QStyle,
    QStyledItemDelegate,
    QVBoxLayout,
    QWidget,
)

from ..image_qt import file_to_pixmap, pil_to_pixmap
from ...core.models import BulkProposal, GameItem
from ...core.placeholder import ensure_no_cover_asset
from ...config.settings import load_settings, ui_settings
from ...i18n import tr, translate_status
from ..theme import template_palette
from .labels import quality_text, quality_tooltip, region_to_flag

log = logging.getLogger(__name__)

class GamesTableModel(QAbstractTableModel):
    HEADER_KEYS = [
        "table.sel", "table.cover", "table.slot", "table.name", "table.product_id",
        "table.region", "table.status", "table.quality", "table.actions",
    ]
    C_CHECK, C_COVER, C_SLOT, C_NAME, C_PRODUCT, C_REGION, C_STATUS, C_QUALITY, C_ACTIONS = range(9)
    checked_changed = Signal(int, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._games: list[GameItem] = []
        self._bulk_checked: dict[int, bool] = {}
        self._proposals: dict[int, BulkProposal] = {}
        self._bulk_mode: bool = False
        self._pixmap_cache: dict[str, QPixmap] = {}

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._games)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.HEADER_KEYS)

    def headerData(self, section: int, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            if section == self.C_CHECK and self._bulk_mode:
                return ""
            return tr(self.HEADER_KEYS[section])
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.ToolTipRole and section == self.C_CHECK:
            return "Seleccionar/deseleccionar todos"
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._games):
            return None
        game = self._games[index.row()]
        col = index.column()
        proposal = self._proposals.get(game.slot)

        if role == Qt.ItemDataRole.DisplayRole:
            return self._display(game, col, proposal)
        if role == Qt.ItemDataRole.UserRole and col == self.C_COVER:
            return self._cover_pixmap(game, proposal)
        if role == Qt.ItemDataRole.CheckStateRole and col == self.C_CHECK and self._bulk_mode:
            return Qt.CheckState.Checked if self._bulk_checked.get(game.slot, False) else Qt.CheckState.Unchecked
        if role == Qt.ItemDataRole.TextAlignmentRole and col in (self.C_REGION, self.C_STATUS, self.C_QUALITY, self.C_SLOT):
            return int(Qt.AlignmentFlag.AlignCenter)
        if role == Qt.ItemDataRole.ToolTipRole:
            return self._tooltip(game, col, proposal)
        if role == Qt.ItemDataRole.ForegroundRole:
            return self._foreground(game, col, proposal)
        if role == Qt.ItemDataRole.BackgroundRole:
            return self._background(game, col, proposal)
        return None

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole) -> bool:
        if index.column() == self.C_CHECK and role == Qt.ItemDataRole.CheckStateRole:
            slot = self._games[index.row()].slot
            checked = value == Qt.CheckState.Checked.value
            self._bulk_checked[slot] = checked
            self.dataChanged.emit(index, index, [role])
            self.headerDataChanged.emit(Qt.Orientation.Horizontal, self.C_CHECK, self.C_CHECK)
            self.checked_changed.emit(slot, checked)
            return True
        return False

    def flags(self, index):
        base = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if index.column() == self.C_CHECK and self._bulk_mode:
            base |= Qt.ItemFlag.ItemIsUserCheckable
        return base

    def set_games(self, games: list[GameItem]):
        self.beginResetModel()
        self._games = list(games)
        self.endResetModel()

    def set_bulk_mode(self, enabled: bool, checked: dict[int, bool] | None = None):
        self._bulk_mode = enabled
        if checked is not None:
            self._bulk_checked = dict(checked)
        if self._games:
            self.dataChanged.emit(self.index(0, self.C_CHECK), self.index(self.rowCount() - 1, self.C_CHECK))
        self.headerDataChanged.emit(Qt.Orientation.Horizontal, self.C_CHECK, self.C_CHECK)

    def set_proposals(self, proposals: dict[int, BulkProposal]):
        self._proposals = proposals
        if self._games:
            self.dataChanged.emit(self.index(0, 0), self.index(self.rowCount() - 1, self.C_QUALITY))

    def invalidate_slot(self, slot: int):
        for row, game in enumerate(self._games):
            if game.slot == slot:
                self._pixmap_cache.pop(f"proposal_{slot}", None)
                if game.current_cover:
                    self._pixmap_cache.pop(str(game.current_cover), None)
                self.dataChanged.emit(self.index(row, 0), self.index(row, self.C_QUALITY))
                return

    def clear_cache(self):
        self._pixmap_cache.clear()

    def _display(self, game: GameItem, col: int, proposal) -> str | None:
        if col in (self.C_CHECK, self.C_COVER, self.C_ACTIONS):
            return None
        if col == self.C_SLOT:
            return f"{game.slot:03d}"
        if col == self.C_NAME:
            return game.name
        if col == self.C_PRODUCT:
            return game.product_id
        if col == self.C_REGION:
            return region_to_flag(game.region)
        if col == self.C_STATUS:
            return self._status_text(game, proposal)
        if col == self.C_QUALITY:
            if proposal and proposal.quality is not None and proposal.status in {"seleccionada", "revision", "omitida"}:
                return getattr(proposal.quality, "label", "?") or "?"
            return quality_text(game)
        return None

    def _status_text(self, game: GameItem, proposal) -> str:
        if game.pending_delete:
            return "pendiente_eliminar"
        if game.pending_add:
            return "pendiente_guardar"
        if game.has_placeholder_cover:
            return "sin_caratula"
        if proposal and proposal.status == "seleccionada":
            return "propuesta_auto"
        if proposal and proposal.status == "revision":
            return "revision"
        if proposal and proposal.status in {"omitida", "error"}:
            return proposal.status
        return game.status

    def _tooltip(self, game: GameItem, col: int, proposal) -> str | None:
        if col == self.C_REGION:
            return game.region or tr("region.unknown")
        if col == self.C_STATUS:
            status = self._status_text(game, proposal)
            text = _status_tooltip(status)
            if proposal and proposal.reason:
                return f"{text}\nReason: {proposal.reason}"
            return text
        if col == self.C_QUALITY:
            if proposal and proposal.quality is not None:
                quality = proposal.quality
                source = proposal.candidate.display if proposal.candidate else "-"
                reason = f"\nMotivo: {proposal.reason}" if proposal.reason else ""
                return (
                    f"Proposed quality: {quality.label}\n"
                    f"Quality score: {quality.score}\n"
                    f"Original: {quality.width}x{quality.height}\n"
                    f"Candidate: {source}{reason}"
                )
            return quality_tooltip(game)
        if col == self.C_COVER:
            if proposal and proposal.image is not None:
                return tr("cover.click_proposal")
            if game.current_cover:
                return tr("cover.click_current")
            return tr("cover.none")
        return None

    def _foreground(self, game: GameItem, col: int, proposal) -> QColor | None:
        palette = template_palette()
        if col == self.C_STATUS:
            fg_map = {
                "correcta": palette["success"], "seleccionada": palette["accent"],
                "propuesta_auto": palette["accent_text"], "revision": palette["warning"],
                "pendiente_guardar": palette["accent_text"],
                "guardado": palette["success"], "dudosa": palette["warning"],
                "sin_caratula": palette["warning"], "pendiente_eliminar": palette["danger"],
                "faltante": palette["danger"], "omitida": palette["muted"],
                "error": palette["danger"], "no_revisada": palette["muted"],
            }
            return QColor(fg_map.get(self._status_text(game, proposal), palette["muted"]))
        if col == self.C_QUALITY:
            label = getattr(proposal.quality, "label", "") if proposal and proposal.quality else game.quality_label
            fg_map = {
                "Alta": palette["success"], "Aceptable": palette["accent_text"],
                "Baja": palette["warning"], "Rechazar": palette["danger"],
            }
            return QColor(fg_map.get(label, palette["muted"]))
        return None

    def _background(self, game: GameItem, col: int, proposal) -> QColor | None:
        palette = template_palette()
        if col == self.C_STATUS:
            bg_map = {
                "correcta": palette["success_soft"], "seleccionada": palette["accent_soft"],
                "propuesta_auto": palette["accent_soft"], "revision": palette["warning_soft"],
                "pendiente_guardar": palette["accent_soft"],
                "guardado": palette["success_soft"], "dudosa": palette["warning_soft"],
                "sin_caratula": palette["warning_soft"], "pendiente_eliminar": palette["danger_soft"],
                "faltante": palette["danger_soft"], "omitida": palette["surface_alt"],
                "error": palette["danger_soft"], "no_revisada": palette["surface_alt"],
            }
            return QColor(bg_map.get(self._status_text(game, proposal), palette["surface_alt"]))
        if col == self.C_QUALITY:
            label = getattr(proposal.quality, "label", "") if proposal and proposal.quality else game.quality_label
            bg_map = {
                "Alta": palette["success_soft"], "Aceptable": palette["accent_soft"],
                "Baja": palette["warning_soft"], "Rechazar": palette["danger_soft"],
            }
            return QColor(bg_map.get(label, palette["surface_alt"]))
        return None

    def _cover_pixmap(self, game: GameItem, proposal) -> QPixmap | None:
        if proposal and proposal.image is not None and proposal.status in {"seleccionada", "revision"}:
            key = f"proposal_{game.slot}"
            if key not in self._pixmap_cache:
                try:
                    self._pixmap_cache[key] = pil_to_pixmap(proposal.image, (92, 92))
                except Exception:
                    return None
            return self._pixmap_cache[key]
        if game.current_cover and Path(game.current_cover).exists():
            key = str(game.current_cover)
            if key not in self._pixmap_cache:
                try:
                    self._pixmap_cache[key] = file_to_pixmap(game.current_cover, (92, 92))
                except Exception:
                    return None
            return self._pixmap_cache[key]
        if game.has_placeholder_cover or game.status == "faltante":
            placeholder = ensure_no_cover_asset()
            key = str(placeholder)
            if key not in self._pixmap_cache:
                try:
                    self._pixmap_cache[key] = file_to_pixmap(placeholder, (92, 92))
                except Exception:
                    return None
            return self._pixmap_cache[key]
        return None

    def bulk_mode_active(self) -> bool:
        return self._bulk_mode

    def bulk_header_check_state(self) -> Qt.CheckState:
        if not self._games:
            return Qt.CheckState.Unchecked
        checked = [bool(self._bulk_checked.get(game.slot, False)) for game in self._games]
        if all(checked):
            return Qt.CheckState.Checked
        if any(checked):
            return Qt.CheckState.PartiallyChecked
        return Qt.CheckState.Unchecked


def _status_tooltip(status: str) -> str:
    return tr("status.tooltip", status=translate_status(status))

