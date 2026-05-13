from __future__ import annotations

import logging
import os
import webbrowser
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QEvent, QObject, QRect, QSize, Qt, QThread, QTimer
from PySide6.QtGui import QAction, QActionGroup, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QDialog,
    QGraphicsDropShadowEffect,
    QStyle,
    QStyleOptionButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from .. import APP_NAME, REPOSITORY_URL
from .dialogs import (
    AboutDialog, AddGameDialog, BackupPromptDialog, BulkProgressDialog, CandidateDialog, ConfirmApplyDialog,
    CoverPreviewDialog, LanguageSelectionDialog, ProviderSettingsDialog, SetupWizardDialog,
)
from ..core.image_quality import NORMALIZATION_MODE, analyze_image, apply_quality_report
from ..core.models import BulkProposal, Candidate, GameItem, RomLibraryEntry, VALID_STATES
from ..config.paths import (
    BASE_DIR, INBOX_DIR, LOG_PATH, REPORT_JSON, REPORT_TSV, STATE_PATH, migrate_legacy_runtime_data,
)
from ..i18n import (
    active_language, available_languages, refresh_languages, set_language, tr, translate_status,
)
from ..core.placeholder import ensure_no_cover_asset
from ..reports.exporter import export_report, export_reports
from ..dreamcast.scanner import load_cover_index_map, scan_sd_root
from ..covers.search import best_auto_candidate, load_candidate_image
from ..config.settings import (
    active_template as configured_active_template,
    configured_languages_dir,
    configured_template_dir,
    load_settings,
    save_settings,
    set_ui_preference,
    set_active_template as persist_active_template,
)
from ..config.state import load_state, update_game_state
from ..dreamcast.storage_diagnostics import StorageDiagnostic
from ..services.bulk_service import valid_cover_proposals
from ..services.backup_service import backup_decision
from ..services.sd_registry import registered_backup_exists
from ..services.cover_service import persist_cover_selection
from ..services.game_service import build_pending_game, next_free_slot
from ..services.sd_slot_transaction import SdSlotTransactionService, incomplete_slot_transactions
from .icons import action_qicon, app_logo_pixmap, app_qicon, sd_card_qicon, status_qicon
from .theme import (
    apply_template, available_templates, install_template_package, refresh_templates,
    template_label, template_package, template_palette,
)
from .theme_audio import ThemeAudioController
from .widgets import (
    action_button, apply_interactive_cursor, BusyOverlay, chip_label, CONTROL_HEIGHT,
    CoverDelegate, error_details, GamesTableModel, QualityIconDelegate, RegionBadgeDelegate,
    region_to_flag, StatusIconDelegate, ThemeBackgroundWidget,
)
from .workers import (
    AddGamesWorker, BulkWorker, DiagnosticWorker, SaveBulkWorker, SaveChangesWorker, ScanWorker,
    UpdateCheckWorker, start_worker,
)
from .dialogs.about import app_version

STATUS_OPTIONS = ["todos", "no_revisada", "correcta", "dudosa", "faltante", "seleccionada"]
log = logging.getLogger(__name__)


def _bulk_selection_map(games: list[GameItem], checked: bool) -> dict[int, bool]:
    return {game.slot: checked for game in games}


def _product_id_corrections(games: list[GameItem]) -> list[GameItem]:
    return [
        game for game in games
        if game.save_status == "pendiente_guardar"
        and bool(game.previous_product_id)
        and game.previous_product_id != game.product_id
        and not game.pending_add
        and not game.pending_delete
    ]


def _menu_consistency_issues(games: list[GameItem]) -> list[GameItem]:
    return [
        game for game in games
        if game.consistency_warnings
        and not game.pending_add
        and not game.pending_delete
    ]


def _consistency_warning_label(code: str) -> str:
    labels = {
        "slot_compaction_needed": tr("scan_repair.warning.slot_compaction_needed"),
        "folder_without_menu_entry": tr("scan_repair.warning.folder_without_menu_entry"),
        "menu_entry_without_folder": tr("scan_repair.warning.menu_entry_without_folder"),
        "missing_physical_slot": tr("scan_repair.warning.missing_physical_slot"),
    }
    return labels.get(code, code)


def _format_consistency_warnings(warnings: list[str]) -> str:
    return ", ".join(_consistency_warning_label(code) for code in warnings)


def _missing_slots_summary(games: list[GameItem]) -> list[int]:
    slots = {game.slot for game in games if game.slot > 1 and not game.pending_delete}
    if not slots:
        return []
    return sorted(set(range(2, max(slots) + 1)) - slots)


class BulkSelectionHeader(QHeaderView):
    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self.setSectionsClickable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintSection(self, painter, rect, logical_index):
        super().paintSection(painter, rect, logical_index)
        if logical_index != GamesTableModel.C_CHECK:
            return
        model = self.model()
        if not isinstance(model, GamesTableModel) or not model.bulk_mode_active():
            return

        option = QStyleOptionButton()
        option.state = QStyle.StateFlag.State_Enabled
        check_state = model.bulk_header_check_state()
        if check_state == Qt.CheckState.Checked:
            option.state |= QStyle.StateFlag.State_On
        elif check_state == Qt.CheckState.PartiallyChecked:
            option.state |= QStyle.StateFlag.State_NoChange
        else:
            option.state |= QStyle.StateFlag.State_Off

        indicator = self.style().subElementRect(QStyle.SubElement.SE_CheckBoxIndicator, option, self)
        option.rect = QRect(
            rect.x() + (rect.width() - indicator.width()) // 2,
            rect.y() + (rect.height() - indicator.height()) // 2,
            indicator.width(),
            indicator.height(),
        )
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_IndicatorCheckBox, option, painter, self)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        migrate_legacy_runtime_data()
        self.settings = load_settings()
        refresh_languages(configured_languages_dir(self.settings))
        set_language(self.settings.get("ui", {}).get("language", "en"))
        refresh_templates(configured_template_dir(self.settings))
        apply_template(QApplication.instance(), configured_active_template(self.settings))
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_qicon())
        self.resize(1280, 780)
        self.state = load_state(STATE_PATH)
        self.root_path = Path("H:/") if Path("H:/").exists() else Path.cwd()
        self.games: list[GameItem] = []
        self.filtered_games: list[GameItem] = []
        self.scan_thread: QThread | None = None
        self.scan_worker: ScanWorker | None = None
        self.diagnostic_thread: QThread | None = None
        self.diagnostic_worker: DiagnosticWorker | None = None
        self.add_thread: QThread | None = None
        self.add_worker: AddGamesWorker | None = None
        self.save_thread: QThread | None = None
        self.save_worker: SaveChangesWorker | None = None
        self.bulk_thread: QThread | None = None
        self.bulk_worker: BulkWorker | None = None
        self.bulk_dialog: BulkProgressDialog | None = None
        self.save_attention_pulse = False
        self.save_attention_phase = 0
        self.save_attention_timer = QTimer(self)
        self.save_attention_timer.setInterval(550)
        self.save_attention_timer.timeout.connect(self._pulse_save_buttons)
        self.save_bulk_thread: QThread | None = None
        self.save_bulk_worker: SaveBulkWorker | None = None
        self.update_thread: QThread | None = None
        self.update_worker: UpdateCheckWorker | None = None
        self.update_check_notify_current = True
        self.update_check_notify_errors = True
        self.apply_after_bulk_save = False
        self.bulk_mode = False
        self.bulk_checked: dict[int, bool] = {}
        self.bulk_proposals: dict[int, BulkProposal] = {}
        self.games_by_slot: dict[int, GameItem] = {}
        self.slot_cover_map: dict[int, int] = {}
        self.product_cover_map: dict[str, int] = {}
        self.diagnostic: StorageDiagnostic | None = None
        self.write_allowed = False
        self.read_only_reason = "Ruta no diagnosticada."
        self.backup_suggested_roots: set[str] = set()
        self.audio_controller = ThemeAudioController(self)
        try:
            self._build_ui()
            self.apply_theme_runtime()
        except Exception as exc:
            log.critical("MainWindow build failed\n%s", error_details(exc))
            QMessageBox.critical(None, APP_NAME, tr("error.generic", message=exc))

    def _build_ui(self):
        root = ThemeBackgroundWidget()
        layout = QVBoxLayout(root)

        top_bar = QWidget()
        top_bar.setObjectName("TopBar")
        toolbar = QHBoxLayout(top_bar)
        toolbar.setContentsMargins(14, 12, 14, 12)
        self.app_logo = QLabel()
        self.app_logo.setObjectName("AppLogo")
        self.app_logo.setFixedSize(44, 44)
        self.app_logo.setPixmap(app_logo_pixmap(42))
        self.app_logo.setToolTip(APP_NAME)
        toolbar.addWidget(self.app_logo)
        self.path_edit = QLineEdit(str(self.root_path))
        self.path_edit.setFixedHeight(CONTROL_HEIGHT)
        toolbar.addWidget(self.path_edit, 1)
        self.browse_button = action_button(self, "browse", tr("toolbar.path_tooltip"), label=tr("action.route"))
        self.browse_button.setIcon(sd_card_qicon(28))
        self.browse_button.setIconSize(QSize(26, 26))
        self.browse_button.clicked.connect(lambda: self.safe_call(self.pick_root))
        toolbar.addWidget(self.browse_button)
        self.scan_button = action_button(self, "scan", tr("toolbar.scan_tooltip"), variant="accent", label=tr("action.scan"))
        self.scan_button.clicked.connect(lambda: self.safe_call(self.start_scan))
        toolbar.addWidget(self.scan_button)
        self.add_game_button = action_button(self, "add", tr("toolbar.add_tooltip"), variant="success", label=tr("action.add"))
        self.add_game_button.clicked.connect(lambda: self.safe_call(self.open_add_game_dialog))
        self.add_game_button.setEnabled(False)
        toolbar.addWidget(self.add_game_button)
        self.save_changes_button = action_button(self, "save", tr("toolbar.save_tooltip"), variant="success", label=tr("action.save_changes"))
        self.save_changes_button.clicked.connect(lambda: self.safe_call(self.save_changes_to_sd))
        self.save_changes_button.setEnabled(False)
        self.save_changes_button.setText(tr("toolbar.no_changes"))
        self.save_changes_button.setProperty("iconOnly", False)
        self.save_changes_button.setMaximumWidth(16777215)
        self.save_changes_button.setMinimumWidth(156)
        self.save_changes_button.setFixedHeight(CONTROL_HEIGHT)
        toolbar.addWidget(self.save_changes_button)
        layout.addWidget(top_bar)

        filter_bar = QWidget()
        filter_bar.setObjectName("FilterBar")
        filters = QHBoxLayout(filter_bar)
        filters.setContentsMargins(14, 12, 14, 12)
        self.text_filter = QLineEdit()
        self.text_filter.setFixedHeight(CONTROL_HEIGHT)
        self.text_filter.setPlaceholderText(tr("filter.placeholder"))
        self.text_filter.textChanged.connect(lambda _=None: self.safe_call(self.apply_filters))
        filters.addWidget(self.text_filter, 1)
        self.status_filter = QComboBox()
        self.status_filter.setFixedHeight(CONTROL_HEIGHT)
        self.status_filter.setIconSize(QSize(20, 20))
        self._populate_status_filter()
        self.status_filter.currentTextChanged.connect(lambda _=None: self.safe_call(self.apply_filters))
        apply_interactive_cursor(self.status_filter)
        filters.addWidget(self.status_filter)
        self.bulk_mode_button = action_button(self, "bulk_mode", tr("filter.bulk_tooltip"), variant="toggle", checkable=True, label=tr("action.bulk"))
        self.bulk_mode_button.clicked.connect(lambda: self.safe_call(self.toggle_bulk_mode))
        filters.addWidget(self.bulk_mode_button)
        self.bulk_button = action_button(self, "bulk_search", tr("filter.bulk_search_tooltip"), variant="accent", label=tr("action.propose"))
        self.bulk_button.clicked.connect(lambda: self.safe_call(self.start_bulk_search))
        self.bulk_button.setEnabled(False)
        filters.addWidget(self.bulk_button)
        self.save_bulk_button = action_button(self, "save", tr("filter.save_bulk_tooltip"), variant="success", label=tr("action.save"))
        self.save_bulk_button.clicked.connect(lambda: self.safe_call(self.save_bulk_proposals))
        self.save_bulk_button.setEnabled(False)
        self.save_bulk_button.setVisible(False)
        filters.addWidget(self.save_bulk_button)
        self.discard_bulk_button = action_button(self, "discard", tr("filter.discard_bulk_tooltip"), variant="danger", label=tr("action.discard"))
        self.discard_bulk_button.clicked.connect(lambda: self.safe_call(self.discard_bulk_proposals))
        self.discard_bulk_button.setEnabled(False)
        filters.addWidget(self.discard_bulk_button)
        layout.addWidget(filter_bar)

        self._lockable_buttons: list[tuple[QPushButton, str]] = [
            (self.scan_button, "always"),
            (self.add_game_button, "always"),
            (self.save_changes_button, "pending"),
            (self.bulk_mode_button, "always"),
            (self.bulk_button, "bulk_mode"),
            (self.discard_bulk_button, "bulk_any"),
        ]

        self.games_model = GamesTableModel(self)
        self.games_model.checked_changed.connect(self._on_bulk_checked_changed)
        self.table = QTableView()
        self.table.setHorizontalHeader(BulkSelectionHeader(Qt.Orientation.Horizontal, self.table))
        self.table.setModel(self.games_model)
        self.table.setItemDelegateForColumn(GamesTableModel.C_COVER, CoverDelegate(self.table))
        self.table.setItemDelegateForColumn(GamesTableModel.C_REGION, RegionBadgeDelegate(self.table))
        self.table.setItemDelegateForColumn(GamesTableModel.C_STATUS, StatusIconDelegate(self.table))
        self.table.setItemDelegateForColumn(GamesTableModel.C_QUALITY, QualityIconDelegate(self.table))
        self.table.setColumnHidden(GamesTableModel.C_CHECK, True)
        self._apply_table_column_preferences()
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setMouseTracking(True)
        self.table.viewport().setMouseTracking(True)
        self.table.viewport().installEventFilter(self)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.table.setViewportMargins(0, 0, 10, 0)
        self.table.horizontalHeader().setSectionResizeMode(GamesTableModel.C_CHECK, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(GamesTableModel.C_COVER, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(GamesTableModel.C_COVER, 124)
        self.table.horizontalHeader().setSectionResizeMode(GamesTableModel.C_NAME, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(GamesTableModel.C_REGION, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(GamesTableModel.C_REGION, 98)
        self.table.horizontalHeader().setSectionResizeMode(GamesTableModel.C_STATUS, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(GamesTableModel.C_STATUS, 78)
        self.table.horizontalHeader().setSectionResizeMode(GamesTableModel.C_QUALITY, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(GamesTableModel.C_QUALITY, 78)
        self.table.horizontalHeader().setSectionResizeMode(GamesTableModel.C_ACTIONS, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(GamesTableModel.C_ACTIONS, 170)
        self.table.verticalHeader().setDefaultSectionSize(104)
        self.table.verticalHeader().hide()
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.clicked.connect(lambda idx: self.safe_call(lambda: self.handle_table_click(idx.row(), idx.column())))
        self.table.doubleClicked.connect(lambda idx: self.safe_call(lambda: self.open_dialog_for_row(idx.row(), idx.column())))
        self.table.horizontalHeader().sectionClicked.connect(lambda section: self.safe_call(lambda: self.handle_header_click(section)))
        layout.addWidget(self.table, 1)

        bottom = QHBoxLayout()
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        bottom.addWidget(self.progress)
        self.status = QLabel(tr("app.ready"))
        bottom.addWidget(self.status, 1)
        layout.addLayout(bottom)

        self.setCentralWidget(root)
        self.busy_overlay = BusyOverlay(root)
        self.busy_overlay.resize(root.size())

        self.file_menu = self.menuBar().addMenu(tr("menu.file"))
        open_inbox = QAction(action_qicon("inbox"), tr("menu.open_inbox"), self)
        open_inbox.triggered.connect(lambda: self.safe_call(lambda: self.open_path(INBOX_DIR)))
        self.file_menu.addAction(open_inbox)
        open_cache = QAction(action_qicon("cache"), tr("menu.open_cache"), self)
        open_cache.triggered.connect(lambda: self.safe_call(lambda: self.open_path(STATE_PATH.parent)))
        self.file_menu.addAction(open_cache)
        open_log = QAction(action_qicon("log"), tr("menu.open_log"), self)
        open_log.triggered.connect(lambda: self.safe_call(lambda: self.open_path(LOG_PATH)))
        self.file_menu.addAction(open_log)
        self.file_menu.addSeparator()
        export_report_action = QAction(action_qicon("report"), tr("menu.export_report"), self)
        export_report_action.triggered.connect(lambda: self.safe_call(self.export_reports))
        self.file_menu.addAction(export_report_action)
        self.templates_menu = self.menuBar().addMenu(tr("menu.templates"))
        self.template_group = QActionGroup(self)
        self.template_group.setExclusive(True)
        self.rebuild_templates_menu()
        self.language_menu = self.menuBar().addMenu(tr("menu.language"))
        self.language_group = QActionGroup(self)
        self.language_group.setExclusive(True)
        self.rebuild_language_menu()
        self.settings_menu = self.menuBar().addMenu(tr("menu.settings"))
        self._populate_settings_menu()
        self.help_menu = self.menuBar().addMenu(tr("menu.help"))
        about_action = QAction(app_qicon(), tr("menu.about"), self)
        about_action.triggered.connect(lambda: self.safe_call(self.show_about))
        self.help_menu.addAction(about_action)
        update_action = QAction(action_qicon("scan"), tr("menu.check_updates"), self)
        update_action.triggered.connect(lambda: self.safe_call(self.check_for_updates))
        self.help_menu.addAction(update_action)
        self._update_save_button_state()

    def _populate_status_filter(self):
        self.status_filter.clear()
        for status in STATUS_OPTIONS:
            icon = action_qicon("bulk_mode", "default", 22) if status == "todos" else status_qicon(status, 22)
            label = tr("filter.all") if status == "todos" else translate_status(status)
            self.status_filter.addItem(icon, label, status)

    def eventFilter(self, watched, event):
        if getattr(self, "table", None) is not None and watched is self.table.viewport():
            if event.type() == QEvent.Type.MouseMove:
                pos = event.position().toPoint()
                index = self.table.indexAt(pos)
                if index.isValid() and index.column() in (GamesTableModel.C_COVER, GamesTableModel.C_ACTIONS):
                    self.table.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
                else:
                    self.table.viewport().unsetCursor()
            elif event.type() == QEvent.Type.Leave:
                self.table.viewport().unsetCursor()
        return super().eventFilter(watched, event)

    def open_provider_settings(self):
        dialog = ProviderSettingsDialog(self.settings, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.settings = load_settings()
            self.status.setText(tr("dialog.provider.updated"))

    def rebuild_templates_menu(self):
        self.templates_menu.clear()
        self.template_group = QActionGroup(self)
        self.template_group.setExclusive(True)
        active = configured_active_template(self.settings)
        for package in available_templates():
            label = package.name if package.internal else f"{package.name} (external)"
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(active == package.id)
            action.triggered.connect(lambda checked=False, name=package.id: self.safe_call(lambda: self.change_template(name)))
            self.template_group.addAction(action)
            self.templates_menu.addAction(action)
        self.templates_menu.addSeparator()
        install_local = QAction(action_qicon("install_template"), tr("menu.install_template_zip"), self)
        install_local.triggered.connect(lambda: self.safe_call(self.install_template_from_zip))
        self.templates_menu.addAction(install_local)
        install_url = QAction(action_qicon("web"), tr("menu.install_template_url"), self)
        install_url.triggered.connect(lambda: self.safe_call(self.install_template_from_url))
        self.templates_menu.addAction(install_url)
        open_folder = QAction(action_qicon("templates_folder"), tr("menu.open_templates_folder"), self)
        open_folder.triggered.connect(lambda: self.safe_call(self.open_templates_folder))
        self.templates_menu.addAction(open_folder)
        self.templates_menu.addSeparator()
        self.music_action = QAction(action_qicon("music"), tr("menu.music_toggle"), self)
        self.music_action.triggered.connect(lambda: self.safe_call(self.toggle_template_music))
        self.templates_menu.addAction(self.music_action)
        volume_action = QAction(action_qicon("volume"), tr("menu.music_volume"), self)
        volume_action.triggered.connect(lambda: self.safe_call(self.change_music_volume))
        self.templates_menu.addAction(volume_action)
        self.update_music_action()

    def rebuild_language_menu(self):
        self.language_menu.clear()
        self.language_group = QActionGroup(self)
        self.language_group.setExclusive(True)
        active = active_language()
        for language in available_languages():
            label = language.label if language.internal else f"{language.label} (external)"
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(active == language.code)
            action.triggered.connect(lambda checked=False, code=language.code: self.safe_call(lambda: self.change_language(code)))
            self.language_group.addAction(action)
            self.language_menu.addAction(action)
        self.language_menu.addSeparator()
        open_folder = QAction(action_qicon("templates_folder"), tr("menu.open_languages_folder"), self)
        open_folder.triggered.connect(lambda: self.safe_call(self.open_languages_folder))
        self.language_menu.addAction(open_folder)
        reload_action = QAction(action_qicon("scan"), tr("menu.reload_languages"), self)
        reload_action.triggered.connect(lambda: self.safe_call(self.reload_languages))
        self.language_menu.addAction(reload_action)

    def install_template_from_zip(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("menu.install_template_zip"),
            str(configured_template_dir(self.settings)),
            "Template ZIP (*.zip)",
        )
        if not path:
            return
        self.install_template_source(path)

    def install_template_from_url(self):
        url, ok = QInputDialog.getText(self, tr("menu.install_template_url"), tr("template.url_prompt"))
        if not ok or not url.strip():
            return
        self.install_template_source(url.strip())

    def install_template_source(self, source: str):
        if not self._confirm_action(tr("template.trusted_warning"), tr("dialog.backup.continue")):
            return
        try:
            package = install_template_package(source, configured_template_dir(self.settings))
            self.settings = persist_active_template(self.settings, package.id)
            self.rebuild_templates_menu()
            self.apply_theme_runtime()
            self.status.setText(tr("template.installed", name=package.name))
        except Exception as exc:
            log.error("Template install failed: %s", exc, exc_info=True)
            QMessageBox.warning(self, APP_NAME, tr("template.install_failed", message=exc))

    def open_templates_folder(self):
        folder = configured_template_dir(self.settings)
        folder.mkdir(parents=True, exist_ok=True)
        os.startfile(str(folder))

    def toggle_template_music(self):
        if not self.audio_controller.has_music():
            QMessageBox.information(self, APP_NAME, tr("template.no_music"))
            return
        playing = self.audio_controller.play_pause()
        self.settings = set_ui_preference("music_enabled", playing, self.settings)
        self.update_music_action()
        self.status.setText(tr("template.music_playing") if playing else tr("template.music_paused"))

    def change_music_volume(self):
        current = int(self.settings.get("ui", {}).get("music_volume", 35))
        volume, ok = QInputDialog.getInt(self, tr("template.volume_title"), tr("template.volume_label"), current, 0, 100, 5)
        if not ok:
            return
        self.settings = set_ui_preference("music_volume", volume, self.settings)
        self.audio_controller.set_volume(volume)
        self.status.setText(f"{tr('template.volume_title')}: {volume}%")

    def change_language(self, language_code: str):
        selected = set_language(language_code)
        self.settings = set_ui_preference("language", selected, self.settings)
        self.settings = set_ui_preference("language_prompted", True, self.settings)
        self.retranslate_ui()
        language = next((item for item in available_languages() if item.code == selected), None)
        self.status.setText(tr("language.changed", name=language.label if language else selected))

    def reload_languages(self):
        refresh_languages(configured_languages_dir(self.settings))
        set_language(self.settings.get("ui", {}).get("language", "en"))
        self.rebuild_language_menu()
        self.status.setText(tr("language.reloaded"))

    def open_languages_folder(self):
        folder = configured_languages_dir(self.settings)
        folder.mkdir(parents=True, exist_ok=True)
        os.startfile(str(folder))

    def retranslate_ui(self):
        self.menuBar().clear()
        self._populate_status_filter()
        self.text_filter.setPlaceholderText(tr("filter.placeholder"))
        self.save_changes_button.setToolTip(tr("toolbar.save_tooltip"))
        self._update_save_button_state()
        self.games_model.headerDataChanged.emit(Qt.Orientation.Horizontal, 0, self.games_model.columnCount() - 1)
        self.file_menu = self.menuBar().addMenu(tr("menu.file"))
        open_inbox = QAction(action_qicon("inbox"), tr("menu.open_inbox"), self)
        open_inbox.triggered.connect(lambda: self.safe_call(lambda: self.open_path(INBOX_DIR)))
        self.file_menu.addAction(open_inbox)
        open_cache = QAction(action_qicon("cache"), tr("menu.open_cache"), self)
        open_cache.triggered.connect(lambda: self.safe_call(lambda: self.open_path(STATE_PATH.parent)))
        self.file_menu.addAction(open_cache)
        open_log = QAction(action_qicon("log"), tr("menu.open_log"), self)
        open_log.triggered.connect(lambda: self.safe_call(lambda: self.open_path(LOG_PATH)))
        self.file_menu.addAction(open_log)
        self.file_menu.addSeparator()
        export_report_action = QAction(action_qicon("report"), tr("menu.export_report"), self)
        export_report_action.triggered.connect(lambda: self.safe_call(self.export_reports))
        self.file_menu.addAction(export_report_action)
        self.templates_menu = self.menuBar().addMenu(tr("menu.templates"))
        self.rebuild_templates_menu()
        self.language_menu = self.menuBar().addMenu(tr("menu.language"))
        self.rebuild_language_menu()
        self.settings_menu = self.menuBar().addMenu(tr("menu.settings"))
        self._populate_settings_menu()
        self.help_menu = self.menuBar().addMenu(tr("menu.help"))
        about_action = QAction(app_qicon(), tr("menu.about"), self)
        about_action.triggered.connect(lambda: self.safe_call(self.show_about))
        self.help_menu.addAction(about_action)
        update_action = QAction(action_qicon("scan"), tr("menu.check_updates"), self)
        update_action.triggered.connect(lambda: self.safe_call(self.check_for_updates))
        self.help_menu.addAction(update_action)
        self.populate_table()

    def _populate_settings_menu(self):
        providers_action = QAction(action_qicon("web"), tr("menu.online_sources"), self)
        providers_action.triggered.connect(lambda: self.safe_call(self.open_provider_settings))
        self.settings_menu.addAction(providers_action)
        backup_action = QAction(action_qicon("templates_folder"), tr("menu.backup_current_sd"), self)
        backup_action.triggered.connect(lambda: self.safe_call(self.force_backup_current_sd))
        self.settings_menu.addAction(backup_action)
        self.settings_menu.addSeparator()
        self.show_status_column_action = QAction(action_qicon("bulk_mode"), tr("menu.show_status_column"), self)
        self.show_status_column_action.setCheckable(True)
        self.show_status_column_action.setChecked(self._status_column_enabled())
        self.show_status_column_action.triggered.connect(
            lambda checked=False: self.safe_call(lambda: self.toggle_status_column(bool(checked)))
        )
        self.settings_menu.addAction(self.show_status_column_action)
        self._apply_table_column_preferences()

    def _status_column_enabled(self) -> bool:
        return bool(self.settings.get("ui", {}).get("show_status_column", False))

    def _apply_table_column_preferences(self):
        status_visible = self._status_column_enabled()
        if hasattr(self, "table"):
            self.table.setColumnHidden(GamesTableModel.C_STATUS, not status_visible)
        if hasattr(self, "status_filter"):
            self.status_filter.setVisible(status_visible)
            if not status_visible and self.status_filter.currentData() != "todos":
                self.status_filter.blockSignals(True)
                index = self.status_filter.findData("todos")
                self.status_filter.setCurrentIndex(max(index, 0))
                self.status_filter.blockSignals(False)
        if hasattr(self, "show_status_column_action"):
            self.show_status_column_action.setChecked(status_visible)

    def toggle_status_column(self, visible: bool):
        self.settings = set_ui_preference("show_status_column", bool(visible), self.settings)
        self._apply_table_column_preferences()
        self.apply_filters()

    def show_about(self):
        AboutDialog(self).exec()

    def check_for_updates(self, notify_current: bool = True, notify_errors: bool = True):
        if self.update_thread is not None and self.update_thread.isRunning():
            return
        self.update_check_notify_current = notify_current
        self.update_check_notify_errors = notify_errors
        self.status.setText(tr("updates.checking"))
        worker = UpdateCheckWorker(app_version())
        self._start_worker(
            worker,
            "update_thread",
            "update_worker",
            on_finished=self.update_check_finished,
            on_error=self.update_check_error,
        )

    def update_check_finished(self, result: dict):
        if not result.get("ok"):
            if self.update_check_notify_current:
                QMessageBox.information(self, APP_NAME, tr("updates.no_release"))
            self.status.setText(tr("updates.no_release"))
            return
        current = str(result.get("current", app_version()))
        latest = str(result.get("latest", ""))
        url = str(result.get("url", REPOSITORY_URL))
        if result.get("newer"):
            if self._confirm_action(
                tr("updates.available", current=current, latest=latest, url=url),
                tr("updates.open_release"),
            ):
                webbrowser.open(url)
        else:
            if self.update_check_notify_current:
                QMessageBox.information(self, tr("updates.current.title"), tr("updates.current", current=current))
        self.status.setText(tr("updates.current", current=current) if not result.get("newer") else tr("updates.available.title"))

    def update_check_error(self, message: str):
        if self.update_check_notify_errors:
            self.show_error(tr("updates.error", message=message))
        else:
            log.info("Startup update check failed: %s", message)
            self.status.setText("")

    def check_for_startup_updates(self):
        if bool(self.settings.get("ui", {}).get("check_updates_on_startup", True)):
            self.check_for_updates(notify_current=False, notify_errors=False)

    def update_music_action(self):
        if not hasattr(self, "music_action"):
            return
        if not self.audio_controller.has_music():
            self.music_action.setEnabled(False)
            self.music_action.setText(tr("menu.music_unavailable"))
            return
        self.music_action.setEnabled(True)
        self.music_action.setText(tr("menu.music_pause") if self.audio_controller.is_playing() else tr("menu.music_play"))

    def apply_theme_runtime(self):
        selected = apply_template(QApplication.instance(), configured_active_template(self.settings))
        if selected != configured_active_template(self.settings):
            self.settings = persist_active_template(self.settings, selected)
            if hasattr(self, "templates_menu"):
                self.rebuild_templates_menu()
        package = template_package(selected)
        ui = self.settings.get("ui", {})
        if isinstance(self.centralWidget(), ThemeBackgroundWidget):
            self.centralWidget().apply_theme_background(package, bool(ui.get("background_enabled", True)))
        self.audio_controller.apply_theme(package, int(ui.get("music_volume", 35)), enabled=False)
        self.update_music_action()

    def pick_root(self):
        folder = QFileDialog.getExistingDirectory(self, tr("toolbar.path_tooltip"), self.path_edit.text())
        if folder:
            self.path_edit.setText(folder)

    def start_scan(self):
        self.root_path = Path(self.path_edit.text())
        log.info("Scan requested: %s", self.root_path)
        self.status.setText(tr("scan.diagnosing"))
        if self.scan_thread is not None and self.scan_thread.isRunning():
            QMessageBox.information(self, APP_NAME, tr("scan.already_running"))
            return
        if self.diagnostic_thread is not None and self.diagnostic_thread.isRunning():
            QMessageBox.information(self, APP_NAME, tr("scan.diagnostic_running"))
            return
        self.start_busy(tr("scan.diagnosing"), str(self.root_path))
        self._start_worker(
            DiagnosticWorker(self.root_path),
            "diagnostic_thread", "diagnostic_worker",
            on_finished=self.finish_diagnostic,
            on_error=self.diagnostic_error,
        )

    def finish_diagnostic(self, diagnostic: StorageDiagnostic):
        self.diagnostic = diagnostic
        self.write_allowed = diagnostic.write_allowed
        self.read_only_reason = "" if diagnostic.write_allowed else diagnostic.reason
        log.info(
            "Diagnostic finished: route=%s health=%s menu=%s write=%s scan=%s",
            diagnostic.route_class, diagnostic.storage_health, diagnostic.menu_state,
            diagnostic.write_allowed, diagnostic.scan_allowed,
        )
        if not diagnostic.scan_allowed:
            self.stop_busy()
            self.status.setText(diagnostic.reason)
            self.open_setup_wizard(diagnostic)
            return
        if self._handle_incomplete_slot_transactions():
            return
        if self._should_suggest_backup(diagnostic):
            self.backup_suggested_roots.add(str(diagnostic.root.resolve()))
            self.stop_busy()
            self.status.setText(tr("scan.backup_required"))
            if not self.open_backup_prompt(diagnostic):
                self.write_allowed = False
                self.read_only_reason = "Decision de respaldo pendiente."
                self.add_game_button.setEnabled(False)
                self._update_save_button_state()
                self.status.setText(tr("scan.cancelled_backup_pending"))
                return
            self.settings = load_settings()
            self.write_allowed = diagnostic.write_allowed
            self.read_only_reason = "" if diagnostic.write_allowed else diagnostic.reason
            self.start_busy(tr("scan.scanning"), str(self.root_path))
            self.status.setText(tr("scan.scanning"))
            self.games_model.set_games([])
            self.games_model.clear_cache()
            self._start_worker(
                ScanWorker(self.root_path, self.state),
                "scan_thread", "scan_worker",
                on_finished=self.finish_scan,
                on_error=self.scan_error,
            )
            return
        self.status.setText(tr("scan.scanning"))
        self.games_model.set_games([])
        self.games_model.clear_cache()
        self._start_worker(
            ScanWorker(self.root_path, self.state),
            "scan_thread", "scan_worker",
            on_finished=self.finish_scan,
            on_error=self.scan_error,
        )

    def _handle_incomplete_slot_transactions(self) -> bool:
        transactions = incomplete_slot_transactions(self.root_path)
        if not transactions:
            return False
        self.stop_busy()
        tx_dir = transactions[0]
        message = QMessageBox(self)
        message.setWindowTitle(APP_NAME)
        message.setIcon(QMessageBox.Icon.Warning)
        message.setText(tr("slot_recovery.title"))
        message.setInformativeText(tr("slot_recovery.body", path=tx_dir))
        complete = message.addButton(tr("slot_recovery.complete"), QMessageBox.ButtonRole.AcceptRole)
        revert = message.addButton(tr("slot_recovery.revert"), QMessageBox.ButtonRole.DestructiveRole)
        open_folder = message.addButton(tr("slot_recovery.open_folder"), QMessageBox.ButtonRole.ActionRole)
        later = message.addButton(tr("slot_recovery.later"), QMessageBox.ButtonRole.RejectRole)
        message.setDefaultButton(complete)
        message.exec()
        clicked = message.clickedButton()
        service = SdSlotTransactionService(self.root_path, tx_dir.name)
        try:
            if clicked is complete:
                service.complete_from_state()
                self.status.setText(tr("slot_recovery.completed"))
                self.start_scan()
            elif clicked is revert:
                service.revert_from_state()
                self.status.setText(tr("slot_recovery.reverted"))
                self.start_scan()
            elif clicked is open_folder:
                webbrowser.open(str(tx_dir))
                self.status.setText(tr("slot_recovery.pending"))
            elif clicked is later:
                self.status.setText(tr("slot_recovery.pending"))
        except Exception as exc:
            self.show_error(tr("slot_recovery.failed", message=exc))
        return True

    def diagnostic_error(self, message: str):
        self.write_allowed = False
        self.read_only_reason = message
        self.stop_busy()
        self.show_error(tr("error.diagnostic", message=message))

    def finish_scan(self, games: list[GameItem]):
        try:
            log.info("Scan UI finish: %s games", len(games))
            self.games = games
            self.games_by_slot = {g.slot: g for g in games}
            self.slot_cover_map, self.product_cover_map = load_cover_index_map()
            self.apply_filters()
            suffix = "" if self.write_allowed else tr("readonly.suffix", reason=self.read_only_reason)
            self.status.setText(tr("scan.finished", count=len(games), path=self.root_path, suffix=suffix))
            self.stop_busy()
            QTimer.singleShot(0, self._show_scan_repair_prompt)
        except Exception as exc:
            self.stop_busy()
            self.show_error(tr("scan.display_failed", message=exc))

    def _show_scan_repair_prompt(self):
        corrections = _product_id_corrections(self.games)
        consistency_issues = _menu_consistency_issues(self.games)
        missing_slots = _missing_slots_summary(self.games)
        if not corrections and not consistency_issues and not missing_slots:
            return
        lines = []
        if missing_slots:
            visible_slots = ", ".join(f"{slot:03d}" for slot in missing_slots[:16])
            if len(missing_slots) > 16:
                visible_slots += f", {tr('product_id.more_items', count=len(missing_slots) - 16)}"
            lines.append(tr("scan_repair.missing_slots", slots=visible_slots))
            moved_count = len([
                game for game in consistency_issues
                if "slot_compaction_needed" in game.consistency_warnings
            ])
            if moved_count:
                lines.append(tr("scan_repair.compaction_consequence", count=moved_count))
        non_compaction_issues = [
            game for game in consistency_issues
            if any(code != "slot_compaction_needed" for code in game.consistency_warnings)
        ]
        shown_issue_games = 0
        for game in non_compaction_issues:
            warnings = [code for code in game.consistency_warnings if code != "slot_compaction_needed"]
            if warnings and len(lines) < 12:
                lines.append(f"{game.slot:03d} - {game.name}: {_format_consistency_warnings(warnings)}")
                shown_issue_games += 1
        shown_corrections = 0
        for game in corrections[:12 - len(lines)]:
            lines.append(f"{game.slot:03d} - {game.name}: {game.previous_product_id} -> {game.product_id}")
            shown_corrections += 1
        hidden = (len(non_compaction_issues) - shown_issue_games) + (len(corrections) - shown_corrections)
        if hidden > 0:
            lines.append(tr("product_id.more_items", count=hidden))
        message = QMessageBox(self)
        message.setWindowTitle(APP_NAME)
        message.setIcon(QMessageBox.Icon.Warning)
        message.setText(tr("scan_repair.prompt_title", count=len(consistency_issues), product_count=len(corrections)))
        detail = "\n".join(lines)
        informative = tr("scan_repair.prompt_body")
        if detail:
            informative = f"{informative}\n\n{tr('scan_repair.affected_intro')}\n{detail}"
        message.setInformativeText(informative)
        save_button = None
        if self.write_allowed:
            save_button = message.addButton(tr("scan_repair.save_now"), QMessageBox.ButtonRole.AcceptRole)
        later_button = message.addButton(tr("scan_repair.later"), QMessageBox.ButtonRole.RejectRole)
        message.setDefaultButton(save_button or later_button)
        message.exec()
        if save_button is not None and message.clickedButton() is save_button:
            self.save_changes_to_sd(confirm=False)

    def scan_error(self, message: str):
        self.stop_busy()
        self.show_error(message)

    def apply_filters(self):
        try:
            needle = self.text_filter.text().lower().strip()
            status = str(self.status_filter.currentData() or "todos") if self._status_column_enabled() else "todos"
            self.filtered_games = []
            for game in self.games:
                hay = f"{game.slot:03d} {game.name} {game.product_id}".lower()
                if needle and needle not in hay:
                    continue
                if status != "todos" and game.status != status:
                    continue
                self.filtered_games.append(game)
            self.populate_table()
        except Exception as exc:
            self.show_error(tr("error.filter", message=exc))

    def populate_table(self):
        log.info("Populating table: %s visible games", len(self.filtered_games))
        self.table.setColumnHidden(GamesTableModel.C_CHECK, not self.bulk_mode)
        self.games_model.set_bulk_mode(self.bulk_mode, self.bulk_checked)
        self.games_model.set_proposals(self.bulk_proposals)
        self.games_model.set_games(self.filtered_games)
        for row, game in enumerate(self.filtered_games):
            self._set_row_actions(row, game)
        self.save_changes_button.setEnabled(self.write_allowed and self.has_pending_changes())
        self._update_save_button_state()
        self._update_bulk_delete_button_state()

    def _set_row_actions(self, row: int, game: GameItem):
        actions = QWidget()
        actions.setStyleSheet("background: transparent;")
        actions.setMinimumWidth(164)
        action_layout = QHBoxLayout(actions)
        action_layout.setContentsMargins(8, 8, 8, 8)
        action_layout.setSpacing(8)
        action_layout.addStretch(1)
        search = action_button(self, "search", tr("game.action_cover"), width=44, variant="accent")
        search.setFixedSize(58, 58)
        search.clicked.connect(lambda _=False, g=game: self.safe_call(lambda: self.open_dialog(g)))
        action_layout.addWidget(search)
        delete_variant = "danger" if not game.pending_delete else "accent"
        delete_tooltip = tr("game.mark_delete") if not game.pending_delete else tr("game.unmark_delete")
        delete = action_button(self, "close", delete_tooltip, width=44, variant=delete_variant)
        delete.setFixedSize(58, 58)
        delete.clicked.connect(lambda _=False, g=game: self.safe_call(lambda: self.toggle_delete_game(g)))
        delete.setEnabled(self.write_allowed or (game.pending_add and game.is_new))
        action_layout.addWidget(delete)
        action_layout.addStretch(1)
        self.table.setIndexWidget(self.games_model.index(row, GamesTableModel.C_ACTIONS), actions)

    def open_dialog_for_row(self, row: int, col: int):
        if col == GamesTableModel.C_COVER:
            return
        if 0 <= row < len(self.filtered_games):
            self.open_dialog(self.filtered_games[row])

    def handle_table_click(self, row: int, col: int):
        if col != GamesTableModel.C_COVER or not (0 <= row < len(self.filtered_games)):
            return
        game = self.filtered_games[row]
        dialog = CoverPreviewDialog(game, self.bulk_proposals.get(game.slot), self)
        dialog.exec()

    def handle_header_click(self, section: int):
        if section != GamesTableModel.C_CHECK or not self.bulk_mode:
            return
        self.toggle_bulk_header_selection()

    def open_dialog(self, game: GameItem):
        dialog = CandidateDialog(game, self, auto_search=True)
        dialog.selected.connect(lambda cand, image, g=game: self.save_selected_cover(g, cand, image))
        dialog.name_saved.connect(lambda name, g=game: self.save_game_name(g, name))
        dialog.exec()

    def open_add_game_dialog(self):
        if not self.ensure_write_allowed():
            return
        dialog = AddGameDialog(self.settings, self.games, self)
        dialog.selected.connect(self.add_games_from_entries)
        dialog.exec()

    def add_games_from_entries(self, entries: list[RomLibraryEntry]):
        if self.add_thread is not None and self.add_thread.isRunning():
            QMessageBox.information(self, APP_NAME, tr("game.prepare_running"))
            return
        self.start_busy(tr("game.prepare"), tr("game.prepare_count", count=len(entries)))
        worker = AddGamesWorker(
            entries,
            self.games,
            self.slot_cover_map,
            self.product_cover_map,
            self.state,
            self.root_path,
        )
        self._start_worker(
            worker,
            "add_thread",
            "add_worker",
            on_finished=self.add_games_finished,
            on_error=self.add_games_error,
            extra=[(worker.progress, self.add_games_progress)],
        )

    def add_games_progress(self, current: int, total: int, name: str, status_text: str):
        self.progress.setVisible(True)
        self.progress.setRange(0, total)
        self.progress.setValue(current)
        if hasattr(self, "busy_overlay"):
            self.busy_overlay.show_message(status_text, name)
        self.status.setText(tr("game.prepare_progress", status=status_text, name=name))

    def add_games_finished(self, result: dict):
        added_games = list(result.get("games", []))
        skipped = int(result.get("skipped", 0) or 0)
        self.games.extend(added_games)
        self.games.sort(key=lambda item: item.slot)
        for game in added_games:
            self.games_by_slot[game.slot] = game
        self.apply_filters()
        self.stop_busy()
        if added_games:
            suffix = f" {skipped} omitidos por falta de slot." if skipped else ""
            self.status.setText(tr("game.added_memory", count=len(added_games), suffix=suffix))
        elif skipped:
            QMessageBox.warning(self, APP_NAME, tr("game.no_slots"))
            self.status.setText(tr("game.no_slots_status"))

    def add_games_error(self, message: str):
        self.stop_busy()
        self.show_error(tr("game.prepare_failed", message=message))

    def add_game_from_entry(self, entry: RomLibraryEntry):
        if self._add_game_from_entry(entry, show_errors=True):
            self.apply_filters()
            self.status.setText(tr("game.added_one"))

    def _add_game_from_entry(self, entry: RomLibraryEntry, show_errors: bool) -> bool:
        if not self.ensure_write_allowed():
            return False
        slot = next_free_slot(self.games)
        if slot is None:
            if show_errors:
                QMessageBox.warning(self, APP_NAME, tr("game.no_slots"))
            return False
        game = build_pending_game(
            entry,
            slot,
            self.slot_cover_map.get(slot) or self.product_cover_map.get((entry.product_id or "").upper()),
        )
        self._seed_cover_for_new_game(game)
        self.games.append(game)
        self.games.sort(key=lambda item: item.slot)
        self.games_by_slot[slot] = game
        return True

    def _seed_cover_for_new_game(self, game: GameItem):
        try:
            candidate = best_auto_candidate(game, game.name, include_remote=False)
            if candidate is not None:
                image = load_candidate_image(candidate)
                quality = analyze_image(image)
                self._persist_cover_selection(game, candidate, image, quality, "seleccionada", persist_state=False)
                game.has_placeholder_cover = False
                return
        except Exception:
            log.exception("Could not resolve local cover for new game: slot=%03d", game.slot)

        placeholder_path = ensure_no_cover_asset()
        game.current_cover = placeholder_path
        game.selected_image = ""
        game.original_image = ""
        game.preview_image = ""
        game.selected_source = ""
        game.selected_score = 0
        game.quality_label = ""
        game.quality_score = 0
        game.status = "faltante"
        game.has_placeholder_cover = True

    def toggle_delete_game(self, game: GameItem):
        if not (game.pending_add and game.is_new) and not self.ensure_write_allowed():
            return
        if game.pending_add and game.is_new:
            if not self._confirm_action(
                tr("game.discard_new_title", slot=f"{game.slot:03d}", name=game.name),
                tr("action.discard"),
            ):
                return
            self.games = [item for item in self.games if item is not game]
            self.games_by_slot.pop(game.slot, None)
            self.apply_filters()
            self.status.setText(tr("game.discarded", slot=f"{game.slot:03d}"))
            return

        if game.pending_delete:
            game.pending_delete = False
            game.save_status = ""
            self.apply_filters()
            self.status.setText(tr("game.delete_unmarked", slot=f"{game.slot:03d}"))
            return

        if not self._confirm_action(
            tr("game.delete_confirm", slot=f"{game.slot:03d}", name=game.name),
            tr("game.mark_delete"),
        ):
            return
        game.pending_delete = True
        game.save_status = "pendiente_eliminar"
        self.apply_filters()
        self.status.setText(tr("game.delete_marked", slot=f"{game.slot:03d}"))

    def has_pending_changes(self) -> bool:
        return self.pending_change_count() > 0

    def pending_change_count(self) -> int:
        game_changes = sum(
            1
            for game in self.games
            if (
                game.pending_add
                or game.pending_delete
                or game.save_status in {"pendiente_guardar", "pendiente_eliminar"}
            )
        )
        return game_changes + self._valid_bulk_proposal_count()

    def _valid_bulk_proposal_count(self) -> int:
        return len(valid_cover_proposals(self.bulk_proposals))

    def _pending_apply_counts(self, cover_override: int | None = None) -> dict[str, int]:
        additions = len([game for game in self.games if game.pending_add])
        deletions = len([game for game in self.games if game.pending_delete])
        if cover_override is None:
            covers = len([
                game for game in self.games
                if game.save_status == "pendiente_guardar"
                and not game.pending_delete
                and bool(game.selected_image)
                and Path(game.selected_image).exists()
                and not game.has_placeholder_cover
            ])
            covers += self._valid_bulk_proposal_count()
        else:
            covers = cover_override
        plan = SdSlotTransactionService(self.root_path, "preview").build_plan(self.games)
        return {
            "covers": covers,
            "additions": additions,
            "deletions": deletions,
            "slot_moves": len(plan.moves),
            "product_updates": len(_product_id_corrections(self.games)),
        }

    def _update_save_button_state(self):
        if not hasattr(self, "save_changes_button"):
            return
        count = self.pending_change_count()
        has_changes = count > 0 and self.write_allowed
        self.save_changes_button.setEnabled(has_changes)
        self.save_changes_button.setText(tr("action.save_changes") if count else tr("toolbar.no_changes"))
        self.save_changes_button.setToolTip(
            tr("toolbar.save_tooltip_count", count=count)
            if count
            else tr("toolbar.save_tooltip")
        )
        self.save_changes_button.setProperty("attention", "true" if has_changes else "false")
        if not has_changes:
            self.save_changes_button.setProperty("pulse", "false")
            self._clear_button_glow(self.save_changes_button)
        elif self.save_changes_button.property("pulse") != "true":
            self.save_attention_pulse = True
            self.save_changes_button.setProperty("pulse", "true")
            self._apply_button_glow(self.save_changes_button)
        self._repolish(self.save_changes_button)
        self._update_attention_timer()

    def _update_bulk_save_button_attention(self, saveable: int | None = None):
        if not hasattr(self, "save_bulk_button"):
            return
        if not self.save_bulk_button.isVisible():
            self.save_bulk_button.setEnabled(False)
            self.save_bulk_button.setProperty("attention", "false")
            self.save_bulk_button.setProperty("pulse", "false")
            self._clear_button_glow(self.save_bulk_button)
            return
        if saveable is None:
            saveable = len(valid_cover_proposals(self.bulk_proposals))
        has_bulk_action = saveable > 0 and self.save_bulk_button.isEnabled()
        self.save_bulk_button.setProperty("attention", "true" if has_bulk_action else "false")
        if not has_bulk_action:
            self.save_bulk_button.setProperty("pulse", "false")
            self._clear_button_glow(self.save_bulk_button)
        self._repolish(self.save_bulk_button)
        self._update_attention_timer()

    def _update_attention_timer(self):
        has_save_attention = (
            hasattr(self, "save_changes_button")
            and self.save_changes_button.property("attention") == "true"
        )
        has_bulk_attention = (
            hasattr(self, "save_bulk_button")
            and self.save_bulk_button.property("attention") == "true"
        )
        if has_save_attention or has_bulk_attention:
            if not self.save_attention_timer.isActive():
                self.save_attention_timer.start()
        else:
            self.save_attention_pulse = False
            self.save_attention_phase = 0
            self.save_attention_timer.stop()

    def _pulse_save_buttons(self):
        self.save_attention_pulse = not self.save_attention_pulse
        self.save_attention_phase = (self.save_attention_phase + 1) % 8
        if hasattr(self, "save_changes_button") and self.save_changes_button.property("attention") == "true":
            if not self.write_allowed or not self.has_pending_changes():
                self._update_save_button_state()
            else:
                self.save_changes_button.setProperty("pulse", "true" if self.save_attention_pulse else "false")
                self._apply_button_glow(self.save_changes_button)
                self._repolish(self.save_changes_button)
        if hasattr(self, "save_bulk_button") and self.save_bulk_button.property("attention") == "true":
            if not self.save_bulk_button.isEnabled() or not valid_cover_proposals(self.bulk_proposals):
                self._update_bulk_save_button_attention(0)
            else:
                self.save_bulk_button.setProperty("pulse", "true" if self.save_attention_pulse else "false")
                self._apply_button_glow(self.save_bulk_button)
                self._repolish(self.save_bulk_button)

    def _apply_button_glow(self, button: QPushButton):
        effect = button.graphicsEffect()
        if not isinstance(effect, QGraphicsDropShadowEffect):
            effect = QGraphicsDropShadowEffect(button)
            button.setGraphicsEffect(effect)
        effect.setBlurRadius(28 if self.save_attention_pulse else 12)
        effect.setOffset(0, 0)
        effect.setColor(QColor(41, 243, 167, 210 if self.save_attention_pulse else 95))

    def _clear_button_glow(self, button: QPushButton):
        if button.graphicsEffect() is not None:
            button.setGraphicsEffect(None)

    def _pulse_save_button(self):
        if not self.write_allowed or not self.has_pending_changes():
            self._update_save_button_state()
            return
        self.save_attention_pulse = not self.save_attention_pulse
        self.save_changes_button.setProperty("pulse", "true" if self.save_attention_pulse else "false")
        self._repolish(self.save_changes_button)

    def _repolish(self, widget: QWidget):
        fixed_height = widget.minimumHeight() if widget.minimumHeight() == widget.maximumHeight() else None
        fixed_width = widget.minimumWidth() if widget.minimumWidth() == widget.maximumWidth() else None
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        if fixed_width is not None:
            widget.setFixedWidth(fixed_width)
        if fixed_height is not None:
            widget.setFixedHeight(fixed_height)
        widget.update()

    def save_changes_to_sd(self, confirm: bool = True):
        if not self.ensure_write_allowed():
            return
        if not self.has_pending_changes():
            QMessageBox.information(self, APP_NAME, tr("save.none"))
            return
        if self.save_thread is not None and self.save_thread.isRunning():
            QMessageBox.information(self, APP_NAME, tr("save.running"))
            return
        if self._valid_bulk_proposal_count():
            self.save_bulk_proposals(confirm=confirm)
            return
        if confirm:
            counts = self._pending_apply_counts()
            dialog = ConfirmApplyDialog(
                self.root_path,
                counts["covers"],
                counts["additions"],
                counts["deletions"],
                self,
                slot_moves=counts["slot_moves"],
                product_updates=counts["product_updates"],
            )
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
        self.start_busy(tr("action.save_changes"), str(self.root_path))
        _w = SaveChangesWorker(self.root_path, self.games, self.state, write_allowed=self.write_allowed)
        self._start_worker(
            _w, "save_thread", "save_worker",
            on_finished=self.save_finished,
            on_error=self.save_error,
            extra=[(_w.progress, self.save_progress)],
        )

    def save_progress(self, current: int, total: int, name: str, status_text: str):
        self.progress.setVisible(True)
        self.progress.setRange(0, total)
        self.progress.setValue(current)
        if hasattr(self, "busy_overlay"):
            self.busy_overlay.show_message(status_text, name)
        self.status.setText(tr("save.progress", status=status_text, name=name))

    def save_finished(self, message: str):
        self.stop_busy()
        QMessageBox.information(self, APP_NAME, message)
        self.status.setText(message)
        self.start_scan()

    def save_error(self, message: str):
        self.stop_busy()
        self.show_error(tr("save.failed", message=message))

    def save_game_name(self, game: GameItem, new_name: str):
        new_name = new_name.strip()
        if not new_name:
            return
        game.name = new_name
        game.save_status = "pendiente_guardar"
        log.info("Name corrected: slot=%03d name=%s", game.slot, new_name)
        if not game.pending_add:
            update_game_state(STATE_PATH, self.state, self.root_path, game)
        self.apply_filters()
        self.status.setText(tr("game.name_saved", slot=f"{game.slot:03d}", name=new_name))

    def save_selected_cover(self, game: GameItem, candidate: Candidate, image: Image.Image):
        try:
            log.info("Saving selected cover: slot=%03d source=%s score=%s", game.slot, candidate.source, candidate.score)
            self.start_busy(tr("cover.saving"), game.name)
            quality = analyze_image(image)
            if not quality.accepted:
                self.stop_busy()
                QMessageBox.warning(self, APP_NAME, tr("cover.rejected", quality=quality.display, warning=quality.warning))
                return
            if quality.label == "Baja":
                self.stop_busy()
                if not self._confirm_action(
                    tr("cover.low_question", quality=quality.display, warning=quality.warning),
                    tr("cover.use_anyway"),
                ):
                    return
                self.start_busy(tr("cover.saving"), game.name)
            normalized_path = self._persist_cover_selection(
                game, candidate, image, quality, "seleccionada",
                persist_state=not game.pending_add,
            )
            game.has_placeholder_cover = False
            self.apply_filters()
            self.status.setText(tr("cover.saved", path=normalized_path))
            self.stop_busy()
        except Exception as exc:
            self.stop_busy()
            self.show_error(tr("cover.save_failed", message=exc))

    def _persist_cover_selection(self, game: GameItem, candidate: Candidate, image: Image.Image,
                                  quality, status: str, persist_state: bool = True) -> Path:
        return persist_cover_selection(
            game,
            candidate,
            image,
            quality,
            status,
            state_path=STATE_PATH,
            state=self.state,
            root_path=self.root_path,
            persist_state=persist_state,
        )

    def set_status(self, game: GameItem, status: str):
        if status not in VALID_STATES:
            return
        game.status = status
        log.info("Status changed: slot=%03d status=%s", game.slot, status)
        if not game.pending_add:
            update_game_state(STATE_PATH, self.state, self.root_path, game)
        self.apply_filters()

    def toggle_bulk_mode(self):
        self.bulk_mode = not self.bulk_mode
        self.bulk_mode_button.setChecked(self.bulk_mode)
        if self.bulk_mode:
            self.bulk_checked = {
                game.slot: game.status in {"faltante", "dudosa", "no_revisada"}
                for game in self.games
            }
            self.games_model.set_bulk_mode(True, self.bulk_checked)
            self.bulk_button.setEnabled(True)
            self.status.setText(tr("bulk.enabled"))
        else:
            self.bulk_checked.clear()
            self.games_model.set_bulk_mode(False, {})
            self.bulk_button.setEnabled(False)
            self.status.setText(tr("bulk.disabled"))
        self._update_bulk_delete_button_state()
        self.apply_filters()

    def _on_bulk_checked_changed(self, slot: int, checked: bool):
        self.bulk_checked[slot] = checked
        self._update_bulk_delete_button_state()

    def _selected_bulk_games(self) -> list[GameItem]:
        if not self.bulk_mode:
            return []
        return [game for game in self.games if self.bulk_checked.get(game.slot, False)]

    def _bulk_delete_targets(self) -> list[GameItem]:
        return [
            game for game in self._selected_bulk_games()
            if not game.pending_delete and not (game.pending_add and game.is_new)
        ]

    def _update_bulk_delete_button_state(self):
        if not hasattr(self, "discard_bulk_button"):
            return
        delete_count = len(self._bulk_delete_targets())
        has_delete_targets = delete_count > 0 and self.write_allowed
        has_proposals = bool(self.bulk_proposals)
        self.discard_bulk_button.setEnabled(has_delete_targets or has_proposals)
        if has_proposals:
            text = tr("action.discard")
            tooltip = tr("filter.discard_bulk_tooltip")
        elif has_delete_targets:
            text = tr("action.delete")
            tooltip = tr("bulk.delete_selected_tooltip", count=delete_count)
        else:
            text = tr("action.discard")
            tooltip = tr("filter.discard_bulk_tooltip")
        if not self.discard_bulk_button.property("iconOnly"):
            self.discard_bulk_button.setText(text)
        self.discard_bulk_button.setToolTip(tooltip)
        self.discard_bulk_button.setAccessibleName(tooltip)

    def toggle_bulk_header_selection(self):
        if not self.bulk_mode:
            return
        select_all = not all(self.bulk_checked.get(game.slot, False) for game in self.games)
        self.bulk_checked = _bulk_selection_map(self.games, select_all)
        self.games_model.set_bulk_mode(True, self.bulk_checked)
        self.apply_filters()
        self._update_bulk_delete_button_state()
        if select_all:
            self.status.setText(tr("bulk.selected_all", count=len(self.games)))
        else:
            self.status.setText(tr("bulk.selected_none"))

    def start_bulk_search(self):
        if not self.bulk_mode:
            self.toggle_bulk_mode()
        targets = [g for g in self.games if self.bulk_checked.get(g.slot, False)]
        if not targets:
            QMessageBox.information(self, APP_NAME, tr("bulk.no_targets"))
            return
        if self.bulk_thread is not None and self.bulk_thread.isRunning():
            QMessageBox.information(self, APP_NAME, tr("bulk.running"))
            return
        self.bulk_proposals.clear()
        self.bulk_button.setEnabled(False)
        self.bulk_mode_button.setEnabled(False)
        self.scan_button.setEnabled(False)
        self.save_bulk_button.setEnabled(False)
        self.discard_bulk_button.setEnabled(False)
        self.status.setText(tr("bulk.started"))
        self.bulk_dialog = BulkProgressDialog(len(targets), self)
        self.bulk_dialog.cancel_requested.connect(self.cancel_bulk_search)
        _bw = BulkWorker(targets)
        self._start_worker(
            _bw, "bulk_thread", "bulk_worker",
            on_finished=self.finish_bulk,
            on_error=self.bulk_error,
            extra=[(_bw.progress, self.bulk_progress), (_bw.proposal, self.receive_bulk_proposal)],
        )
        self.bulk_dialog.exec()

    def bulk_progress(self, current: int, total: int, name: str, status_text: str):
        if self.bulk_dialog:
            self.bulk_dialog.update_progress(current, total, name, status_text)
        self.status.setText(tr("bulk.progress", status=status_text, name=name))

    def receive_bulk_proposal(self, proposal: BulkProposal):
        self.bulk_proposals[proposal.slot] = proposal

    def cancel_bulk_search(self):
        if self.bulk_worker:
            self.bulk_worker.cancel()
            self.status.setText(tr("bulk.cancelling"))

    def finish_bulk(self, summary: dict):
        try:
            if self.bulk_dialog:
                self.bulk_dialog.accept()
                self.bulk_dialog = None
            self.bulk_button.setEnabled(True)
            self.bulk_mode_button.setEnabled(True)
            self.scan_button.setEnabled(True)
            saveable = len(valid_cover_proposals(self.bulk_proposals))
            if saveable:
                self.save_bulk_button.setToolTip(tr("bulk.save_ready_tooltip", count=saveable))
                self.save_bulk_button.setAccessibleName(self.save_bulk_button.toolTip())
            else:
                self.save_bulk_button.setToolTip(tr("filter.save_bulk_tooltip"))
                self.save_bulk_button.setAccessibleName(self.save_bulk_button.toolTip())
            self._update_bulk_save_button_attention(saveable)
            self._update_bulk_delete_button_state()
            self.apply_filters()
            self._update_save_button_state()
            summary_key = "bulk.summary_apply" if saveable else "bulk.summary"
            self.status.setText(
                tr(
                    summary_key,
                    processed=summary["processed"],
                    auto=summary["auto"],
                    review=summary["review"],
                    skipped=summary["skipped"],
                    errors=summary["errors"],
                    saveable=saveable,
                )
            )
        except Exception as exc:
            self.show_error(tr("bulk.finished_failed", message=exc))

    def bulk_error(self, message: str):
        if self.bulk_dialog:
            self.bulk_dialog.accept()
            self.bulk_dialog = None
        self.bulk_button.setEnabled(True)
        self.bulk_mode_button.setEnabled(True)
        self.scan_button.setEnabled(True)
        saveable = len(valid_cover_proposals(self.bulk_proposals))
        self._update_bulk_save_button_attention(saveable)
        self._update_bulk_delete_button_state()
        self._update_save_button_state()
        self.show_error(message)

    def save_bulk_proposals(self, confirm: bool = True):
        if self.save_bulk_thread is not None and self.save_bulk_thread.isRunning():
            QMessageBox.information(self, APP_NAME, tr("bulk.save_running"))
            return
        valid = valid_cover_proposals(self.bulk_proposals)
        if not valid:
            QMessageBox.information(self, APP_NAME, tr("bulk.no_valid"))
            return
        items = [(self._game_by_slot(p.slot), p) for p in valid]
        items = [(g, p) for g, p in items if g is not None]
        if not items:
            return
        counts = self._pending_apply_counts(cover_override=len(items))
        if confirm:
            dialog = ConfirmApplyDialog(
                self.root_path,
                counts["covers"],
                counts["additions"],
                counts["deletions"],
                self,
                slot_moves=counts["slot_moves"],
                product_updates=counts["product_updates"],
            )
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
        self.apply_after_bulk_save = True
        self.start_busy(tr("bulk.saving"), f"0 / {len(items)}")
        _sbw = SaveBulkWorker(items)
        self._start_worker(
            _sbw, "save_bulk_thread", "save_bulk_worker",
            on_finished=self._finish_save_bulk,
            on_error=self._save_bulk_error,
            extra=[(_sbw.progress, self._save_bulk_progress)],
        )

    def _save_bulk_progress(self, current: int, total: int, name: str):
        if hasattr(self, "busy_overlay"):
            self.busy_overlay.show_message(tr("bulk.saving"), f"{current} / {total}: {name}")
        self.status.setText(tr("bulk.saving_progress", current=current, total=total, name=name))

    def _finish_save_bulk(self, results: list):
        try:
            saved = 0
            failed = 0
            errors: list[str] = []
            for r in results:
                if r.get("error"):
                    failed += 1
                    log.error("Save bulk slot=%s failed: %s", r["slot"], r["error"])
                    errors.append(f"Slot {int(r['slot']):03d}: {r['error']}")
                    continue
                game = self._game_by_slot(r["slot"])
                if game is None:
                    continue
                game.status = r["status"]
                game.current_cover = Path(r["normalized"])
                game.selected_image = r["normalized"]
                game.original_image = r["original"]
                game.preview_image = r["preview"]
                game.selected_source = r["source"]
                game.selected_score = r["score"]
                game.save_status = "pendiente_guardar" if not game.pending_delete else game.save_status
                game.has_placeholder_cover = False
                apply_quality_report(game, r["quality"], NORMALIZATION_MODE)
                if not game.pending_add:
                    update_game_state(STATE_PATH, self.state, self.root_path, game)
                saved += 1
            self.bulk_proposals.clear()
            self.save_bulk_button.setEnabled(False)
            self.save_bulk_button.setToolTip(tr("filter.save_bulk_tooltip"))
            self.save_bulk_button.setAccessibleName(self.save_bulk_button.toolTip())
            self._update_bulk_save_button_attention(0)
            self._update_bulk_delete_button_state()
            self.apply_filters()
            self._update_save_button_state()
            export_reports(self.games, REPORT_TSV, REPORT_JSON)
            if saved:
                self.status.setText(tr("bulk.saved_apply", count=saved))
                if failed:
                    QMessageBox.warning(
                        self,
                        APP_NAME,
                        tr("bulk.partial_failed", saved=saved, failed=failed, errors="\n".join(errors[:8])),
                    )
                if self.apply_after_bulk_save:
                    QTimer.singleShot(0, lambda: self.save_changes_to_sd(confirm=False))
            elif failed:
                self.status.setText(tr("bulk.none_saved", failed=failed))
                QMessageBox.warning(
                    self,
                    APP_NAME,
                    tr("bulk.none_saved_detail", errors="\n".join(errors[:8])),
                )
            else:
                self.status.setText(tr("bulk.no_proposals"))
        finally:
            self.apply_after_bulk_save = False
            self.stop_busy()

    def _save_bulk_error(self, message: str):
        self.stop_busy()
        self.show_error(tr("bulk.save_error", message=message))

    def discard_bulk_proposals(self):
        if not self.bulk_proposals and self._bulk_delete_targets():
            self.mark_bulk_delete_selected()
            return
        count = len(self.bulk_proposals)
        self.bulk_proposals.clear()
        self.save_bulk_button.setEnabled(False)
        self.save_bulk_button.setToolTip(tr("filter.save_bulk_tooltip"))
        self.save_bulk_button.setAccessibleName(self.save_bulk_button.toolTip())
        self._update_bulk_save_button_attention(0)
        self._update_bulk_delete_button_state()
        self.apply_filters()
        self._update_save_button_state()
        self.status.setText(tr("bulk.discarded", count=count))

    def mark_bulk_delete_selected(self):
        if not self.ensure_write_allowed():
            return
        targets = self._bulk_delete_targets()
        if not targets:
            self._update_bulk_delete_button_state()
            return
        if not self._confirm_bulk_delete(targets):
            return
        for game in targets:
            game.pending_delete = True
            game.save_status = "pendiente_eliminar"
        self.apply_filters()
        self._update_bulk_delete_button_state()
        self.status.setText(tr("bulk.delete_marked", count=len(targets)))

    def _confirm_bulk_delete(self, targets: list[GameItem]) -> bool:
        preview = [f"{game.slot:03d} - {game.name}" for game in targets[:6]]
        if len(targets) > len(preview):
            preview.append(tr("bulk.delete_confirm_more", count=len(targets) - len(preview)))
        full_list = "\n".join(f"{game.slot:03d} - {game.name}" for game in targets)
        message = QMessageBox(self)
        message.setWindowTitle(APP_NAME)
        message.setIcon(QMessageBox.Icon.Question)
        message.setText(tr("bulk.delete_confirm_title", count=len(targets)))
        message.setInformativeText(
            tr(
                "bulk.delete_confirm_body",
                preview="\n".join(preview),
            )
        )
        message.setDetailedText(tr("bulk.delete_confirm_details", games=full_list))
        accept_button = message.addButton(tr("bulk.delete_accept"), QMessageBox.ButtonRole.AcceptRole)
        cancel_button = message.addButton(tr("action.cancel"), QMessageBox.ButtonRole.RejectRole)
        message.setDefaultButton(cancel_button)
        message.exec()
        return message.clickedButton() is accept_button

    def _game_by_slot(self, slot: int) -> GameItem | None:
        return self.games_by_slot.get(slot)

    def export_reports(self):
        try:
            default_path = REPORT_TSV
            path, selected_filter = QFileDialog.getSaveFileName(
                self,
                tr("report.title"),
                str(default_path),
                tr("report.filters"),
            )
            if not path:
                return
            output = Path(path)
            if not output.suffix:
                output = output.with_suffix(".json" if "JSON" in selected_filter else ".tsv")
            self.start_busy(tr("report.busy"), str(output))
            written = export_report(self.games, output)
            self.stop_busy()
            QMessageBox.information(self, APP_NAME, tr("report.done", path=written))
        except Exception as exc:
            self.stop_busy()
            self.show_error(tr("report.failed", message=exc))

    def show_error(self, message: str):
        log.error("UI error: %s", message, exc_info=True)
        self.status.setText(tr("app.error", message=message))
        QMessageBox.warning(self, APP_NAME, message)

    def _confirm_action(self, message_text: str, accept_text: str) -> bool:
        message = QMessageBox(self)
        message.setWindowTitle(APP_NAME)
        message.setIcon(QMessageBox.Icon.Question)
        message.setText(message_text)
        accept_button = message.addButton(accept_text, QMessageBox.ButtonRole.AcceptRole)
        cancel_button = message.addButton(tr("action.cancel"), QMessageBox.ButtonRole.RejectRole)
        message.setDefaultButton(cancel_button)
        message.exec()
        return message.clickedButton() is accept_button

    def open_path(self, path: Path):
        if not Path(path).exists():
            QMessageBox.information(self, APP_NAME, tr("path.missing", path=path))
            return
        os.startfile(str(path))

    def _start_worker(self, worker: QObject, thread_attr: str, worker_attr: str,
                      on_finished, on_error, extra: list | None = None) -> None:
        start_worker(worker, thread_attr, worker_attr, self, on_finished, on_error, extra)

    def ensure_write_allowed(self) -> bool:
        if self.write_allowed:
            return True
        reason = self.read_only_reason or "Current path is not approved for writing."
        QMessageBox.warning(self, APP_NAME, tr("readonly.message", reason=reason))
        return False

    def open_setup_wizard(self, diagnostic: StorageDiagnostic | None = None):
        dialog = SetupWizardDialog(diagnostic, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            self.settings = load_settings()
            return
        self.settings = load_settings()
        if dialog.selected_path:
            self.path_edit.setText(str(dialog.selected_path))
            self.root_path = dialog.selected_path
            self.start_scan()

    def force_backup_current_sd(self):
        if self.diagnostic is None:
            QMessageBox.information(self, APP_NAME, tr("setup.scan_first"))
            return
        self.open_backup_prompt(self.diagnostic, force=True)
        self.settings = load_settings()

    def open_backup_prompt(self, diagnostic: StorageDiagnostic, force: bool = False) -> bool:
        dialog = BackupPromptDialog(diagnostic, self, force=force)
        return dialog.exec() == QDialog.DialogCode.Accepted

    def _should_suggest_backup(self, diagnostic: StorageDiagnostic) -> bool:
        if not diagnostic.scan_allowed:
            return False
        summary = diagnostic.summary
        if summary is None:
            return False
        if diagnostic.route_class not in {"gdemu_structure", "local_backup"}:
            return False
        if not (summary.numeric_dirs or summary.other_entries):
            return False
        root_key = str(diagnostic.root.resolve())
        if root_key in self.backup_suggested_roots:
            return False
        if registered_backup_exists(diagnostic.root):
            return False
        decision = backup_decision(self.settings, diagnostic)
        if decision and decision.get("decision") == "skipped":
            return False
        return True

    def start_busy(self, text: str, detail: str = ""):
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.status.setText(text)
        if hasattr(self, "busy_overlay"):
            self.busy_overlay.show_message(text, detail)
        if hasattr(self, "_lockable_buttons"):
            for btn, _ in self._lockable_buttons:
                btn.setEnabled(False)

    def stop_busy(self):
        self.progress.setVisible(False)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        if hasattr(self, "busy_overlay"):
            self.busy_overlay.clear()
        if hasattr(self, "_lockable_buttons"):
            for btn, mode in self._lockable_buttons:
                if mode == "always":
                    btn.setEnabled(btn is not self.add_game_button or self.write_allowed)
                elif mode == "pending":
                    btn.setEnabled(self.write_allowed and self.has_pending_changes())
                elif mode == "bulk_mode":
                    btn.setEnabled(self.bulk_mode)
                elif mode == "bulk_any":
                    btn.setEnabled(bool(self.bulk_proposals))
        self._update_bulk_save_button_attention()
        self._update_bulk_delete_button_state()
        self._update_save_button_state()

    def change_template(self, template_name: str):
        self.settings = persist_active_template(self.settings, template_name)
        self.apply_theme_runtime()
        self.rebuild_templates_menu()
        self.apply_filters()
        self.status.setText(tr("template.active", name=template_label(configured_active_template(self.settings))))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "busy_overlay"):
            self.busy_overlay.resize(self.centralWidget().size())

    def safe_call(self, callback):
        try:
            callback()
        except Exception as exc:
            log.error("UI callback failed\n%s", error_details(exc))
            self.status.setText(tr("app.error", message=exc))
            QMessageBox.warning(self, APP_NAME, tr("error.generic", message=exc))


def run():
    try:
        log.info("Starting UI")
        _set_windows_app_id()
        app = QApplication([])
        app.setWindowIcon(app_qicon())
        settings = load_settings()
        refresh_languages(configured_languages_dir(settings))
        if not bool(settings.get("ui", {}).get("language_prompted", False)):
            apply_template(app, configured_active_template(settings))
            dialog = LanguageSelectionDialog(available_languages())
            if dialog.exec() == QDialog.DialogCode.Accepted:
                language = dialog.selected_code
            else:
                language = "en"
            settings.setdefault("ui", {})
            settings["ui"]["language"] = language
            settings["ui"]["language_prompted"] = True
            save_settings(settings)
        set_language(settings.get("ui", {}).get("language", "en"))
        refresh_templates(configured_template_dir(settings))
        apply_template(app, configured_active_template(settings))
        window = MainWindow()
        _place_main_window(window)
        window.show()
        QTimer.singleShot(0, lambda: window.safe_call(window.start_scan))
        QTimer.singleShot(1800, lambda: window.safe_call(window.check_for_startup_updates))
        app.exec()
    except Exception as exc:
        log.critical("Fatal startup/runtime error\n%s", error_details(exc))
        QMessageBox.critical(None, APP_NAME, tr("error.generic", message=exc))


def _set_windows_app_id() -> None:
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("openmenu.gdemu.manager")
    except Exception:
        pass


def _place_main_window(window: QMainWindow) -> None:
    screen = QApplication.primaryScreen()
    if screen is None:
        return
    available = screen.availableGeometry()
    width = min(window.width(), max(900, available.width() - 80))
    height = min(window.height(), max(620, available.height() - 80))
    window.resize(width, height)
    x = available.x() + (available.width() - width) // 2
    y = available.y() + (available.height() - height) // 2
    window.move(max(available.x(), x), max(available.y(), y))

