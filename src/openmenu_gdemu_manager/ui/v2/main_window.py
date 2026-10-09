"""V2 composition retaining the original service/transaction controller."""
from pathlib import Path
import copy
import shiboken6
from PySide6.QtCore import Qt,QSize,QTimer
from PySide6.QtWidgets import QApplication,QWidget,QVBoxLayout,QHBoxLayout,QHeaderView,QDialog,QMessageBox
from ... import APP_NAME
from ...i18n import tr as legacy_tr
from ...core.image_quality import analyze_image
from ...services.sd_slot_transaction import incomplete_slot_transactions
from ..main_window import MainWindow
from ..widgets import GamesTableModel,ThemeBackgroundWidget,BusyOverlay
from ..workers import BulkWorker,SaveChangesWorker
from ..dialogs import ConfirmApplyDialog
from ..theme import template_palette
from . import design,catalog
from .catalog import tr
from .design import Button,DestinationButton,label,repolish
from .collection import CollectionModel,CollectionDelegate,CollectionHeader
from .bridge import CoverHost,ProductionWorkspace


class MainWindowV2(MainWindow):
    def __init__(self):
        self._v2_ready=False
        self.cover_host=None
        self.cover_jobs=[]
        self.missing_only=False
        self._rescan_after_worker=False
        self._before_edits={}
        super().__init__()
        self.setWindowTitle(APP_NAME+' · v2')

    def _build_ui(self):
        super()._build_ui()
        old=self.centralWidget()
        root=ThemeBackgroundWidget()
        root.setObjectName('Surface')
        layout=QVBoxLayout(root);layout.setContentsMargins(22,16,22,12);layout.setSpacing(12)
        self.heading=label(tr('collection_title'))
        self.heading.setProperty('collectionHeading',True)
        layout.addWidget(self.heading)
        self.subtitle=label(tr('collection_subtitle'),muted=True)
        layout.addWidget(self.subtitle)
        toolbar=QHBoxLayout()
        self.destination=DestinationButton(self.pick_root,str(self.root_path),tr('destination_unknown'))
        toolbar.addWidget(self.destination,1)
        for button in (self.scan_button,self.add_game_button,self.save_changes_button):
            button.setParent(root);button.setStyleSheet('');button.setFixedHeight(42);toolbar.addWidget(button)
        layout.addLayout(toolbar)
        # Keep the controller's path and browse handles, without duplicate chrome.
        for widget in (self.path_edit,self.browse_button):widget.setParent(root);widget.hide()
        self.guidance=label('',wrap=True);self.guidance.setObjectName('Guidance');layout.addWidget(self.guidance)
        filters=QHBoxLayout()
        self.text_filter.setParent(root);self.text_filter.setFixedHeight(36);filters.addWidget(self.text_filter,1)
        self.missing_button=Button('missing',self.toggle_missing,compact=True)
        self.missing_button.setCheckable(True);filters.addWidget(self.missing_button)
        for widget in (self.status_filter,self.bulk_mode_button,self.bulk_button):
            widget.setParent(root);widget.setStyleSheet('');widget.setFixedHeight(36);filters.addWidget(widget)
        layout.addLayout(filters)
        proposals=QHBoxLayout();proposals.addStretch()
        for widget in (self.save_bulk_button,self.discard_bulk_button):
            widget.setParent(root);widget.setStyleSheet('');widget.setFixedHeight(32);proposals.addWidget(widget)
        layout.addLayout(proposals)
        self.table.setParent(root)
        self.games_model=CollectionModel(self)
        self.games_model.checked_changed.connect(self._on_bulk_checked_changed)
        self.table.setModel(self.games_model)
        self.table.setHorizontalHeader(CollectionHeader(self))
        self.table.horizontalHeader().sectionClicked.connect(self.handle_header_click)
        delegate=CollectionDelegate(self.table)
        self.table.setItemDelegate(delegate)
        for col in range(9):self.table.setItemDelegateForColumn(col,delegate)
        self.table.verticalHeader().setDefaultSectionSize(76)
        self.table.setAlternatingRowColors(False)
        self.table.setViewportMargins(0,0,0,0)
        header=self.table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)
        header.moveSection(header.visualIndex(GamesTableModel.C_SLOT),1)
        for col,width in ((0,78),(1,68),(2,52),(5,110),(6,180),(8,120)):
            header.setSectionResizeMode(col,QHeaderView.ResizeMode.Fixed);self.table.setColumnWidth(col,width)
        header.setSectionResizeMode(3,QHeaderView.ResizeMode.Stretch)
        for col in (4,7):self.table.setColumnHidden(col,True)
        self.table.setColumnHidden(6,False)
        layout.addWidget(self.table,1)
        self.summary=label('',muted=True);layout.addWidget(self.summary)
        for widget in (self.progress,self.status):widget.setParent(root);layout.addWidget(widget)
        self.setCentralWidget(root)
        old.deleteLater()
        self.busy_overlay=BusyOverlay(root)
        self.cover_host=CoverHost(self)
        self._v2_ready=True
        for button in (self.add_game_button,self.save_changes_button,self.bulk_mode_button,self.bulk_button,self.save_bulk_button,self.discard_bulk_button):
            button.setProperty('iconOnly',False)
            button.setMinimumWidth(0)
            button.setMaximumWidth(16777215)
        self.resize(1280,780)
        self.retranslate_ui()

    def retranslate_ui(self):
        super().retranslate_ui()
        if self._v2_ready:
            self.heading.setText(tr('collection_title'));self.subtitle.setText(tr('collection_subtitle'))
            self.missing_button.setText(catalog.action_label('missing'))
            for action in self.menuBar().actions():
                if action.menu():action.menu().aboutToShow.connect(self.leave_bulk)
            self._refresh_controls()

    def _apply_v2_theme(self):
        super().apply_theme_runtime()
        palette=template_palette()
        c=dict(catalog.TOKENS['light'])
        mapping={'bg':'window_bg','surface':'surface','paper':'surface','soft':'surface_soft','ink':'text','muted':'muted','line':'border','focus':'accent_text'}
        for key in ('accent','accent_soft','success','success_soft','danger','danger_soft','warning','warning_soft'):mapping[key]=key
        from ...config.settings import active_template
        if active_template(self.settings)!='basic_formal':
            for key,old in mapping.items():c[key]=palette[old]
        catalog.TOKENS['active']=c
        design.apply_theme(QApplication.instance(),'active')
        app=QApplication.instance()
        app.setStyleSheet(app.styleSheet()+f"QTableView {{background:{c['surface']};border:0;selection-background-color:{c['accent_soft']};}} QHeaderView::section {{background:{c['surface']};color:{c['muted']};border:0;border-bottom:1px solid {c['line']};padding:8px;}}")
        if self._v2_ready:self._refresh_controls()

    def _apply_table_column_preferences(self):
        if not self._v2_ready:return super()._apply_table_column_preferences()
        self.table.setColumnHidden(GamesTableModel.C_STATUS,False)
        self.status_filter.setVisible(self._status_column_enabled())

    def _refresh_controls(self):
        if not self._v2_ready:return
        missing=sum(self.is_missing(g) for g in self.games if not g.pending_delete)
        for button,action in ((self.scan_button,'scan'),(self.add_game_button,'add'),(self.save_changes_button,'save'),(self.bulk_mode_button,'bulk_mode'),(self.bulk_button,'bulk_search'),(self.save_bulk_button,'save'),(self.discard_bulk_button,'discard')):
            button.setIcon(design.icon(catalog.ACTIONS[action]['icon']))
            button.setIconSize(QSize(20,20))
        self.scan_button.setText('');self.scan_button.setFixedWidth(42)
        self.add_game_button.setText(catalog.action_label('add'));self.add_game_button.setProperty('role','primary')
        self.add_game_button.setEnabled(self.write_allowed and not self.operation_running())
        self.save_changes_button.setProperty('role','primary' if self.has_pending_changes() else 'secondary')
        self.bulk_mode_button.setText(catalog.action_label('bulk_mode'))
        self.bulk_mode_button.setProperty('attention',bool(missing) and not self.bulk_mode)
        self.bulk_button.setText(tr('bulk_selection',count=sum(self.bulk_checked.values())))
        self.bulk_button.setVisible(self.bulk_mode)
        self.bulk_button.setEnabled(self.bulk_mode and any(self.bulk_checked.values()) and not self.operation_running())
        self.save_bulk_button.setVisible(bool(self.bulk_proposals));self.discard_bulk_button.setVisible(bool(self.bulk_proposals) or self.bulk_mode)
        self.save_bulk_button.setEnabled(self.write_allowed and bool(self._valid_bulk_proposal_count()) and not self.operation_running())
        if not self.operation_running():self.destination.setEnabled(True)
        summary=self.diagnostic.summary if self.diagnostic else None
        subtitle=tr('destination_ready',filesystem=summary.filesystem or tr('local_folder'),free=f'{summary.free_bytes/1024**3:.1f}') if self.write_allowed and summary else tr('destination_readonly',reason=self.read_only_reason) if self.diagnostic and not self.write_allowed else tr('destination_unknown')
        self.destination.set_destination(str(self.root_path),subtitle)
        self.guidance.setText(tr('destination_readonly',reason=self.read_only_reason) if self.diagnostic and not self.write_allowed else tr('missing_guidance',count=missing) if missing else tr('all_covered') if self.games else tr('destination_empty'))
        self.summary.setText(tr('collection_count',count=len(self.games),missing=missing))
        for button in (self.add_game_button,self.save_changes_button,self.bulk_mode_button):repolish(button)
        for button in (self.add_game_button,self.save_changes_button):
            primary=button.property('role')=='primary'
            button.setIcon(design.icon('plus' if button is self.add_game_button else 'device-floppy',design.colors()['paper'] if primary and button.isEnabled() else design.colors()['ink']))
        self.table.horizontalHeader().viewport().update()

    @staticmethod
    def is_missing(game):return game.has_placeholder_cover or not game.current_cover

    def apply_filters(self):
        if not self._v2_ready:return super().apply_filters()
        needle=self.text_filter.text().strip().casefold()
        status=self.status_filter.currentData() if self._status_column_enabled() else 'todos'
        self.filtered_games=[g for g in self.games if (not needle or needle in f'{g.slot:03d} {g.name} {g.product_id}'.casefold()) and (status in (None,'todos') or g.status==status) and (not self.missing_only or self.is_missing(g))]
        self.populate_table()

    def populate_table(self):
        super().populate_table()
        if self._v2_ready:self._refresh_controls()

    def _set_row_actions(self,row,game):
        if not self._v2_ready:return super()._set_row_actions(row,game)
        actions=QWidget();layout=QHBoxLayout(actions);layout.setContentsMargins(2,4,2,4);layout.setSpacing(4)
        for action,callback in (('search',lambda:self.open_dialog(game)),('info',lambda:self.show_game_info(game)),('remove',lambda:self.toggle_delete_game(game))):
            button=Button(action,lambda _,cb=callback:self.safe_call(cb),compact=True,icon_only=True)
            if action=='remove':button.setEnabled(self.write_allowed and not self.operation_running())
            layout.addWidget(button)
        self.table.setIndexWidget(self.games_model.index(row,GamesTableModel.C_ACTIONS),actions)

    def toggle_missing(self):self.missing_only=self.missing_button.isChecked();self.apply_filters()

    def toggle_bulk_mode(self):
        self.bulk_mode=not self.bulk_mode
        self.bulk_mode_button.setChecked(self.bulk_mode)
        self.bulk_checked={g.slot:self.is_missing(g) and not g.pending_delete for g in self.games} if self.bulk_mode else {}
        self.apply_filters()

    def leave_bulk(self):
        if self.bulk_mode:self.toggle_bulk_mode()

    def _on_bulk_checked_changed(self,slot,checked):
        self.bulk_checked[slot]=checked
        self.games_model.set_bulk_mode(self.bulk_mode,self.bulk_checked)
        self._update_bulk_delete_button_state()
        self._refresh_controls()
        self.table.viewport().update()

    def toggle_bulk_header_selection(self):
        if not self.bulk_mode:return
        targets=[g for g in self.games if not g.pending_delete]
        selected=not all(self.bulk_checked.get(g.slot,False) for g in targets)
        self.bulk_checked={g.slot:selected for g in targets}
        self.apply_filters()

    def handle_table_click(self,row,col):
        if not 0<=row<len(self.filtered_games):return
        game=self.filtered_games[row]
        if self.bulk_mode:
            if col not in (GamesTableModel.C_CHECK,GamesTableModel.C_ACTIONS) and not game.pending_delete:self._on_bulk_checked_changed(game.slot,not self.bulk_checked.get(game.slot,False))
            return
        if col==GamesTableModel.C_COVER:
            view=self.cover_host.store.view(game)
            if view.cover:self.inspect_image(game,view.cover)
            else:self.open_dialog(game)

    def open_dialog_for_row(self,row,col):
        if not self.bulk_mode and col!=GamesTableModel.C_COVER and 0<=row<len(self.filtered_games):self.open_dialog(self.filtered_games[row])

    def _workspace(self,game,auto_search=True):
        view=self.cover_host.store.view(game)
        proposal=self.bulk_proposals.get(game.slot)
        if proposal and proposal.candidate and proposal.image is not None:
            view.proposal=self.cover_host.store.add_candidate(view,proposal.candidate,proposal.image)
            session=self.cover_host.store.session(view)
            if view.proposal not in session.local:session.local.append(view.proposal)
        return ProductionWorkspace(self.cover_host,game,auto_search=auto_search)

    def open_dialog(self,game):
        self.leave_bulk()
        self._workspace(game).exec()
        self.apply_filters()

    def inspect_image(self,game,key,parent=None):
        self.leave_bulk()
        workspace=self._workspace(game,False)
        workspace.inspect(key);workspace.exec()

    def show_game_info(self,game):self.leave_bulk();self.cover_host.show_info(self.cover_host.store.view(game))

    def open_add_game_dialog(self):
        self.leave_bulk()
        if not self.ensure_write_allowed():return
        from .import_games import ImportGamesDialog
        dialog=ImportGamesDialog(self.settings,self.games,self)
        dialog.selected.connect(self.add_games_from_entries)
        dialog.exec()

    def toggle_delete_game(self,game):self.leave_bulk();super().toggle_delete_game(game)

    def save_game_name(self,game,name):
        if self.write_allowed and not self.operation_running():
            self.remember_game(game)
            super().save_game_name(game,name)

    def set_status(self,game,status):
        if self.write_allowed and not self.operation_running():
            self.remember_game(game)
            super().set_status(game,status)

    def remember_game(self,game):
        from ...config.state import game_key
        key=game_key(self.root_path,game.slot)
        if key not in self._before_edits:
            self._before_edits[key]=(game,copy.deepcopy(game.__dict__),copy.deepcopy(self.state.get('games',{}).get(key)))

    def _persist_cover_selection(self,game,*args,**kwargs):
        self.remember_game(game)
        return super()._persist_cover_selection(game,*args,**kwargs)

    def discard_pending_changes(self):
        from ...config.state import flush_state
        from ...config.paths import STATE_PATH
        for key,(game,fields,state) in self._before_edits.items():
            game.__dict__.update(copy.deepcopy(fields))
            if state is None:self.state.setdefault('games',{}).pop(key,None)
            else:self.state.setdefault('games',{})[key]=state
        if self._before_edits:flush_state(STATE_PATH,self.state)
        self._before_edits.clear()
        self.games=[g for g in self.games if not g.pending_add]
        for game in self.games:
            game.pending_delete=False
            if game.save_status=='pendiente_eliminar':game.save_status=''
        self.bulk_proposals.clear()
        self.cover_host.store.clear()
        self.apply_filters()

    def pending_change_count(self):
        count=sum(bool(g.pending_add or g.pending_delete or g.save_status in {'pendiente_guardar','pendiente_eliminar'}) for g in self.games)
        if self.cover_host:
            count+=sum(g.real.save_status not in {'pendiente_guardar','pendiente_eliminar'} and not g.real.pending_add for g in self.cover_host.store.plan())
        return count

    def save_changes_to_sd(self,confirm=True):
        self.leave_bulk()
        if not self.ensure_write_allowed() or self.operation_running():return
        prepared=[]
        if self.cover_host:
            for view in self.cover_host.store.plan():
                if view.real.pending_delete:continue
                key=view.choice;image=self.cover_host.store.image(key);quality=analyze_image(image)
                if not quality.accepted:raise ValueError(quality.warning)
                prepared.append((view,key,image,quality))
        if not self.has_pending_changes():return
        if confirm:
            cover_slots={g.slot for g in self.games if g.save_status=='pendiente_guardar' and bool(g.selected_image) and not g.pending_delete}
            cover_slots.update(view.real.slot for view,_,_,_ in prepared)
            covers=len(cover_slots)
            counts=self._pending_apply_counts(cover_override=covers)
            dialog=ConfirmApplyDialog(self.root_path,counts['covers'],counts['additions'],counts['deletions'],self,slot_moves=counts['slot_moves'],product_updates=counts['product_updates'])
            if dialog.exec()!=QDialog.DialogCode.Accepted:self.apply_filters();return
        # A rejected review must leave the draft, GameItem and local cover
        # library untouched, so Discard/Keep cannot apply a hidden selection.
        for view,key,image,quality in prepared:
            self._persist_cover_selection(view.real,self.cover_host.store.candidate_objects[key],image,quality,'seleccionada',persist_state=not view.real.pending_add)
            view.real.has_placeholder_cover=False
            self.bulk_proposals.pop(view.real.slot,None)
        self.start_busy(legacy_tr('action.save_changes'),str(self.root_path))
        worker=SaveChangesWorker(self.root_path,self.games,self.state,write_allowed=self.write_allowed,validate_images=True)
        self._start_worker(worker,'save_thread','save_worker',on_finished=self.save_finished,on_error=self.save_error,extra=[(worker.progress,self.save_progress)])
        return True

    def save_bulk_proposals(self,confirm=True):
        self.leave_bulk()
        if self.ensure_write_allowed() and not self.operation_running():super().save_bulk_proposals(confirm=confirm)

    def _finish_save_bulk(self,results):
        for result in results:
            if result.get('error'):continue
            game=self._game_by_slot(result['slot'])
            if game is not None:self.remember_game(game)
        super()._finish_save_bulk(results)

    def _start_worker(self,worker,*args,**kwargs):
        if isinstance(worker,BulkWorker):worker.write_allowed=self.write_allowed
        result=super()._start_worker(worker,*args,**kwargs)
        thread=getattr(self,args[0],None)
        if thread is not None:thread.finished.connect(self.refresh_after_worker)
        return result

    def refresh_after_worker(self):
        if not self._v2_ready:return
        if self._rescan_after_worker and not self.operation_running():
            self._rescan_after_worker=False
            self.start_scan()
        else:self.apply_filters()

    def save_finished(self,message):
        self._before_edits.clear()
        self.cover_host.store.clear()
        super().save_finished(message)

    def ensure_write_allowed(self):
        if incomplete_slot_transactions(self.root_path):
            self.write_allowed=False
            self.read_only_reason=legacy_tr('slot_recovery.pending')
            self._refresh_controls()
        return super().ensure_write_allowed()

    def save_error(self,message):
        if incomplete_slot_transactions(self.root_path):
            self.write_allowed=False
            self.read_only_reason=legacy_tr('slot_recovery.pending')
        super().save_error(message)
        self._refresh_controls()

    def operation_running(self):
        for name in ('scan_thread','diagnostic_thread','legacy_upgrade_thread','add_thread','save_thread','bulk_thread','save_bulk_thread'):
            thread=getattr(self,name,None)
            if thread is not None and shiboken6.isValid(thread) and thread.isRunning():return True
        return False

    def finish_scan(self,games):
        if self.cover_host:self.cover_host.store.clear()
        super().finish_scan(games)

    def _can_abandon(self):
        if self.operation_running():return False
        if not self.has_pending_changes():return True
        discard=QMessageBox.question(self,APP_NAME,tr('pending_close'),QMessageBox.StandardButton.Discard|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Cancel)==QMessageBox.StandardButton.Discard
        if discard:self.discard_pending_changes()
        return discard

    def pick_root(self):
        self.leave_bulk()
        if not self._can_abandon():return
        before=self.path_edit.text();super().pick_root()
        if before!=self.path_edit.text():
            self.games=[];self.bulk_proposals.clear();self.cover_host.store.clear();self.start_scan()

    def start_scan(self):
        self.leave_bulk()
        if self.operation_running():
            self._rescan_after_worker=True
            return
        if not self._can_abandon():return
        super().start_scan()

    def open_provider_settings(self):self.leave_bulk();super().open_provider_settings()
    def force_backup_current_sd(self):self.leave_bulk();super().force_backup_current_sd()
    def export_reports(self):self.leave_bulk();super().export_reports()
    def show_about(self):self.leave_bulk();super().show_about()
    def change_language(self,code):self.leave_bulk();super().change_language(code)
    def apply_theme_runtime(self):
        self.leave_bulk()
        return self._apply_v2_theme()

    def start_busy(self,*args):
        super().start_busy(*args)
        if self._v2_ready:self.destination.setEnabled(False)

    def stop_busy(self):
        super().stop_busy()
        if self._v2_ready:self._refresh_controls()

    def closeEvent(self,event):
        update=getattr(self,'update_thread',None)
        running=self.operation_running() or bool(update and shiboken6.isValid(update) and update.isRunning()) or any(shiboken6.isValid(t) and t.isRunning() for t in self.cover_jobs)
        if running:
            QMessageBox.information(self,APP_NAME,tr('close_busy'));event.ignore();return
        if not self._can_abandon():event.ignore();return
        self.audio_controller.stop()
        event.accept()
