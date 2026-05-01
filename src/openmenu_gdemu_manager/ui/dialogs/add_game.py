from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QDir, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QFileSystemModel,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QTreeView,
    QVBoxLayout,
)

from ... import APP_NAME
from ...core.models import GameItem, RomLibraryEntry
from ...config.settings import supported_media_types
from ...dreamcast.rom_library import inspect_source
from ...i18n import tr
from ..widgets import action_button

log = logging.getLogger(__name__)


class AddGameDialog(QDialog):
    selected = Signal(object)

    def __init__(self, settings: dict, existing_games: list[GameItem], parent=None):
        super().__init__(parent)
        self.settings = settings
        self.existing_games = existing_games
        self.supported_media = supported_media_types(settings)
        self.entries: list[RomLibraryEntry] = []
        self.setWindowTitle(tr("dialog.add.title"))
        self.resize(860, 520)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        title = QLabel(tr("dialog.add.heading"))
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        description = QLabel(
            tr("dialog.add.description")
        )
        description.setObjectName("MutedLabel")
        description.setWordWrap(True)
        layout.addWidget(description)

        actions = QHBoxLayout()
        self.pick_files_button = action_button(
            self,
            "local_file",
            tr("dialog.add.pick_files_tip"),
            variant="accent",
            label=tr("dialog.add.files"),
        )
        self.pick_files_button.clicked.connect(self.pick_files)
        actions.addWidget(self.pick_files_button)
        self.pick_folder_button = action_button(
            self,
            "browse",
            tr("dialog.add.pick_folders_tip"),
            label=tr("dialog.add.folders"),
        )
        self.pick_folder_button.clicked.connect(self.pick_folders)
        actions.addWidget(self.pick_folder_button)
        self.remove_button = action_button(
            self,
            "discard",
            tr("dialog.add.remove_tip"),
            variant="danger",
            label=tr("dialog.add.remove"),
        )
        self.remove_button.clicked.connect(self.remove_selected)
        self.remove_button.setEnabled(False)
        actions.addWidget(self.remove_button)
        layout.addLayout(actions)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels([tr("table.name"), "Type", "Path", tr("table.status")])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._sync_buttons)
        layout.addWidget(self.table, 1)

        self.status = QLabel(tr("dialog.add.none"))
        self.status.setObjectName("MutedLabel")
        layout.addWidget(self.status)

        bottom = QHBoxLayout()
        self.add_button = action_button(
            self,
            "select",
            tr("dialog.add.accept_tip"),
            variant="success",
            label=tr("dialog.add.accept"),
        )
        self.add_button.clicked.connect(self.accept_selection)
        self.add_button.setEnabled(False)
        bottom.addWidget(self.add_button)
        close = action_button(self, "close", tr("action.close"), label=tr("action.cancel"))
        close.clicked.connect(self.reject)
        bottom.addWidget(close)
        layout.addLayout(bottom)

    def pick_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            tr("dialog.add.select_games"),
            "",
            "Juegos Dreamcast (*.gdi *.cdi)",
        )
        if not paths:
            return
        self._add_paths([Path(path) for path in paths])

    def pick_folders(self):
        dialog = FolderPickerDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._add_paths(dialog.selected_folders())

    def remove_selected(self):
        rows = sorted({index.row() for index in self.table.selectedIndexes()}, reverse=True)
        for row in rows:
            if 0 <= row < len(self.entries):
                self.entries.pop(row)
        self._refresh_table()

    def accept_selection(self):
        if not self.entries:
            QMessageBox.information(self, APP_NAME, tr("dialog.add.select_one"))
            return
        self.selected.emit(list(self.entries))
        self.accept()

    def _add_paths(self, paths: list[Path]):
        added = 0
        rejected: list[str] = []
        known_paths = {entry.source_path.lower() for entry in self.entries}
        for path in paths:
            entries = self._inspect_selected_path(path)
            if not entries:
                rejected.append(str(path))
                continue
            for entry in entries:
                key = entry.source_path.lower()
                if key in known_paths:
                    continue
                entry.existing_match = self._already_present(entry)
                self.entries.append(entry)
                known_paths.add(key)
                added += 1
        self._refresh_table()
        if rejected:
            QMessageBox.warning(
                self,
                APP_NAME,
                tr("dialog.add.rejected_paths", paths="\n".join(rejected[:8])),
            )
        if added:
            self.status.setText(tr("dialog.add.ready", count=len(self.entries)))

    def _inspect_selected_path(self, path: Path) -> list[RomLibraryEntry]:
        direct = inspect_source(path, self.supported_media)
        if direct is not None:
            return [direct]
        if not path.is_dir():
            return []

        found: dict[str, RomLibraryEntry] = {}
        for child in path.rglob("*"):
            entry = inspect_source(child, self.supported_media)
            if entry is not None:
                found.setdefault(entry.source_path.lower(), entry)
        return sorted(found.values(), key=lambda item: item.name.lower())

    def _already_present(self, entry: RomLibraryEntry) -> bool:
        normalized_name = entry.name.casefold().strip()
        product_id = entry.product_id.upper().strip()
        for game in self.existing_games:
            if normalized_name and game.name.casefold().strip() == normalized_name:
                return True
            if product_id and game.product_id.upper().strip() == product_id:
                return True
        return False

    def _refresh_table(self):
        self.table.setRowCount(len(self.entries))
        for row, entry in enumerate(self.entries):
            self.table.setItem(row, 0, QTableWidgetItem(entry.name))
            self.table.setItem(row, 1, QTableWidgetItem(entry.media_type))
            self.table.setItem(row, 2, QTableWidgetItem(entry.source_path))
            self.table.setItem(row, 3, QTableWidgetItem(tr("dialog.add.exists") if entry.existing_match else tr("dialog.add.new")))
        if not self.entries:
            self.status.setText(tr("dialog.add.none"))
        else:
            self.status.setText(tr("dialog.add.ready", count=len(self.entries)))
        self._sync_buttons()

    def _sync_buttons(self):
        self.add_button.setEnabled(bool(self.entries))
        self.remove_button.setEnabled(bool(self.table.selectedIndexes()))


class FolderPickerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("dialog.add.folder_title"))
        self.resize(820, 560)
        self._build_ui()
        self.set_root(Path.cwd())

    def _build_ui(self):
        layout = QVBoxLayout(self)
        help_text = QLabel(tr("dialog.add.folder_help"))
        help_text.setObjectName("MutedLabel")
        help_text.setWordWrap(True)
        layout.addWidget(help_text)

        root_row = QHBoxLayout()
        self.root_edit = QLineEdit()
        self.root_edit.setReadOnly(True)
        root_row.addWidget(self.root_edit, 1)
        change_root = action_button(self, "browse", tr("dialog.add.change_base"), label=tr("dialog.add.change_base_label"))
        change_root.clicked.connect(self.change_root)
        root_row.addWidget(change_root)
        layout.addLayout(root_row)

        self.model = QFileSystemModel(self)
        self.model.setFilter(QDir.Filter.AllDirs | QDir.Filter.NoDotAndDotDot | QDir.Filter.Drives)
        self.tree = QTreeView()
        self.tree.setModel(self.model)
        self.tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree.setHeaderHidden(True)
        for column in range(1, 4):
            self.tree.setColumnHidden(column, True)
        layout.addWidget(self.tree, 1)

        buttons = QHBoxLayout()
        accept = action_button(self, "select", tr("dialog.add.accept_folders_tip"), variant="success", label=tr("dialog.add.accept_folders"))
        accept.clicked.connect(self.accept)
        buttons.addWidget(accept)
        cancel = action_button(self, "close", tr("action.cancel"), label=tr("action.cancel"))
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)

    def set_root(self, root: Path):
        root = Path(root).resolve()
        self.root_edit.setText(str(root))
        index = self.model.setRootPath(str(root))
        self.tree.setRootIndex(index)

    def change_root(self):
        folder = QFileDialog.getExistingDirectory(self, tr("dialog.add.select_base"), self.root_edit.text())
        if folder:
            self.set_root(Path(folder))

    def selected_folders(self) -> list[Path]:
        rows = self.tree.selectionModel().selectedRows(0)
        folders: list[Path] = []
        seen: set[str] = set()
        for index in rows:
            path = Path(self.model.filePath(index))
            key = str(path).casefold()
            if path.is_dir() and key not in seen:
                folders.append(path)
                seen.add(key)
        return folders
