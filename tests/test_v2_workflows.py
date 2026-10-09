"""Production V2 contracts. Fixtures use generated images and synthetic discs."""
from pathlib import Path
import threading
import pytest
from PIL import Image
from PySide6.QtCore import Qt,QThread
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QMessageBox
from openmenu_gdemu_manager.core.models import GameItem,Candidate,BulkProposal,RomLibraryEntry
from openmenu_gdemu_manager.ui import main_window as legacy
from openmenu_gdemu_manager.ui.v2.main_window import MainWindowV2
from openmenu_gdemu_manager.ui.v2.bridge import ProductionWorkspace
from openmenu_gdemu_manager.ui.v2.import_games import ImportGamesDialog
from openmenu_gdemu_manager.ui.widgets import GamesTableModel
from openmenu_gdemu_manager.ui.v2 import catalog
from openmenu_gdemu_manager.i18n import load_internal_language,set_language


@pytest.fixture
def window(monkeypatch,tmp_path):
    app=QApplication.instance() or QApplication([])
    monkeypatch.setattr(legacy,'migrate_legacy_runtime_data',lambda:None)
    # Fresh portable defaults to the original icon-only preference. V2 must
    # still show the approved icon + label without inheriting its fixed widths.
    monkeypatch.setattr(legacy,'load_settings',lambda:{'ui':{'language':'es','show_button_labels':False}})
    monkeypatch.setattr(legacy,'load_state',lambda path:{})
    monkeypatch.setattr(legacy,'configured_template_dir',lambda _:tmp_path)
    monkeypatch.setattr(legacy,'configured_languages_dir',lambda _:tmp_path)
    def fatal(*args):raise AssertionError(args[-1])
    monkeypatch.setattr(QMessageBox,'critical',fatal)
    w=MainWindowV2();assert w._v2_ready
    w.root_path=tmp_path/'sd';w.root_path.mkdir();w.write_allowed=True
    w.games=[GameItem(2,'Covered',current_cover=tmp_path/'cover.png',product_id='T1234',region='US'),GameItem(3,'Missing',has_placeholder_cover=True,product_id='SLOT003'),GameItem(4,'Another missing',has_placeholder_cover=True)]
    Image.new('RGB',(512,510),'orange').save(tmp_path/'cover.png')
    w.games_by_slot={g.slot:g for g in w.games}
    w.apply_filters();w.show();app.processEvents()
    yield w
    w.games=[];w.cover_host.store.clear();w.close();w.deleteLater();app.processEvents()


def test_bulk_defaults_missing_and_global_all_ignores_filter(window):
    window.toggle_bulk_mode()
    assert window.bulk_checked=={2:False,3:True,4:True}
    window.text_filter.setText('Covered')
    window.toggle_bulk_header_selection()
    assert window.bulk_checked=={2:True,3:True,4:True}
    window.toggle_bulk_header_selection()
    assert not any(window.bulk_checked.values())


def test_setup_declined_pending_changes_preserves_destination_and_games(window, monkeypatch):
    from openmenu_gdemu_manager.ui.v2 import setup
    before=(window.root_path,window.path_edit.text(),list(window.games),window.write_allowed)
    monkeypatch.setattr(window,'_can_abandon',lambda:False)
    def forbidden(*args):raise AssertionError('Setup opened before abandonment approval')
    monkeypatch.setattr(setup,'SetupWizardV2',forbidden)
    window.open_setup_wizard()
    assert (window.root_path,window.path_edit.text(),window.games,window.write_allowed)==before


def test_setup_active_operation_cannot_open_installer(window, monkeypatch):
    from openmenu_gdemu_manager.ui.v2 import setup
    monkeypatch.setattr(window,'operation_running',lambda:True)
    def forbidden(*args):raise AssertionError('Setup opened during active job')
    monkeypatch.setattr(setup,'SetupWizardV2',forbidden)
    window.open_setup_wizard()
    monkeypatch.setattr(window,'operation_running',lambda:False)


def test_setup_new_destination_revokes_old_permissions_before_rescan(window, monkeypatch, tmp_path):
    from openmenu_gdemu_manager.ui.v2 import setup
    from PySide6.QtWidgets import QDialog
    destination=tmp_path/'new-destination';destination.mkdir()
    class Accepted:
        def __init__(self,*args):self.selected_path=destination
        def exec(self):return QDialog.DialogCode.Accepted
    monkeypatch.setattr(setup,'SetupWizardV2',Accepted)
    monkeypatch.setattr(window,'_can_abandon',lambda:True)
    captured=[]
    monkeypatch.setattr(window,'start_scan',lambda:captured.append((window.root_path,list(window.games),window.write_allowed)))
    window.open_setup_wizard()
    assert captured==[(destination,[],False)] and window.games_by_slot=={}


def test_diagnostic_dialog_handoff_waits_for_thread_cleanup(window, monkeypatch):
    from openmenu_gdemu_manager.dreamcast.storage_diagnostics import diagnose_storage
    diagnostic=diagnose_storage(window.root_path)
    running=[True];called=[]
    monkeypatch.setattr(window,'operation_running',lambda:running[0])
    monkeypatch.setattr(legacy.MainWindow,'finish_diagnostic',lambda self,d:called.append(d))
    window.finish_diagnostic(diagnostic)
    assert not called and window._pending_diagnostic is diagnostic
    running[0]=False
    window.refresh_after_worker()
    assert called==[diagnostic] and window._pending_diagnostic is None


def test_initial_unrelated_working_directory_opens_destination_choice(window,monkeypatch):
    from pathlib import Path
    window.root_path=Path.cwd()
    calls=[]
    monkeypatch.setattr(window,'open_setup_wizard',lambda diagnostic=None:calls.append(diagnostic))
    window.start_scan()
    assert calls==[None]


def test_row_and_checkbox_toggle_once_and_actions_leave_bulk(window,monkeypatch):
    window.toggle_bulk_mode()
    row=0;index=window.games_model.index(row,GamesTableModel.C_NAME)
    QTest.mouseClick(window.table.viewport(),Qt.MouseButton.LeftButton,pos=window.table.visualRect(index).center())
    assert window.bulk_checked[2]
    checkbox=window.games_model.index(row,GamesTableModel.C_CHECK)
    QTest.mouseClick(window.table.viewport(),Qt.MouseButton.LeftButton,pos=window.table.visualRect(checkbox).center())
    assert not window.bulk_checked[2]
    called=[]
    monkeypatch.setattr(window.cover_host,'show_info',lambda game:called.append(window.bulk_mode))
    window.show_game_info(window.games[0])
    assert called==[False] and window.bulk_checked=={}


def test_metadata_preserved_and_name_search_are_separate(window,monkeypatch):
    game=window.games[1]
    game.internal_name='DISC ORIGINAL';game.disc='2/2';game.vga='0';game.version='V1.003';game.date='20010201';game.artwork_serials=['T1234']
    workspace=ProductionWorkspace(window.cover_host,game,auto_search=False)
    workspace.gallery.query.setText('Different search')
    assert game.name=='Missing' and game.internal_name=='DISC ORIGINAL'
    monkeypatch.setattr(legacy,'update_game_state',lambda *args:None)
    workspace.rename()
    assert game.name=='Different search' and game.save_status=='pendiente_guardar'
    assert (game.disc,game.vga,game.version,game.date,game.artwork_serials)==('2/2','0','V1.003','20010201',['T1234'])
    workspace.reject()


@pytest.mark.parametrize('size',[(1280,780),(1024,720),(900,620)])
def test_gallery_six_whole_images_and_reachable_buttons(window,size):
    store=window.cover_host.store;game=window.games[1];view=store.view(game);session=store.session(view)
    for i in range(8):
        candidate=Candidate('test',f'Variant {i}',90,local_path=f'fixture-{i}',region=('JP','US','EU')[i%3])
        key=store.add_candidate(view,candidate,Image.new('RGB',(512+i,500+i),(180+i*5,70,20)))
        session.results.append(key)
    ws=ProductionWorkspace(window.cover_host,game,auto_search=False);ws.resize(*size);ws.show();QTest.qWait(60)
    assert len(ws.gallery.cards)==6 and ws.gallery.next.isEnabled()
    for position,card in enumerate(ws.gallery.cards):
        button_bottom=card.choose.mapTo(card,card.choose.rect().bottomRight())
        assert button_bottom.y()<card.height()
        assert all(not card.geometry().intersects(previous.geometry()) for previous in ws.gallery.cards[:position])
        assert card.image.pm.width()>=512
    last=ws.gallery.cards[-1]
    ws.gallery.scroll.ensureWidgetVisible(last.choose);QApplication.processEvents()
    p=last.choose.mapTo(ws.gallery.scroll.viewport(),last.choose.rect().bottomRight())
    assert p.y()<ws.gallery.scroll.viewport().height()
    ws.gallery.page(1);assert len(ws.gallery.cards)==2
    ws.reject()


def test_drafts_do_not_touch_sd_and_viewer_uses_original_normalizer(window):
    from openmenu_gdemu_manager.core.image_quality import normalize_cover
    from openmenu_gdemu_manager.ui.image_qt import pil_to_pixmap
    before=list(window.root_path.rglob('*'));game=window.games[1];store=window.cover_host.store;view=store.view(game)
    image=Image.new('RGB',(512,510),'red');candidate=Candidate('local','Red',95,local_path='generated')
    key=store.add_candidate(view,candidate,image)
    assert store.choose(view,key)=='chosen' and window.has_pending_changes()
    assert list(window.root_path.rglob('*'))==before and not game.selected_image
    ws=ProductionWorkspace(window.cover_host,game,auto_search=False)
    actual=ws.normalized_pixmap(key).toImage();expected=pil_to_pixmap(normalize_cover(image),(256,256)).toImage()
    assert actual==expected
    ws.inspect(key);viewer=ws.stack.currentWidget();viewer.set_mode(True)
    assert viewer.views[0].item.pixmap().toImage()==expected
    ws.reject()


def test_readonly_blocks_mutations_and_stale_search_ignored(window):
    game=window.games[1];store=window.cover_host.store;view=store.view(game);window.write_allowed=False
    key=store.add_candidate(view,Candidate('test','Test',90),Image.new('RGB',(512,512),'red'))
    assert store.choose(view,key)=='blocked'
    assert not store.rename(view,'Changed') and game.name=='Missing'
    ws=ProductionWorkspace(window.cover_host,game,auto_search=False)
    ws.reject();ws.search_finished({'items':[(Candidate('test','Late',95),Image.new('RGB',(512,512)), '')],'query':'late'},ws.search_request)
    assert not store.session(view).results


def test_import_selection_invalid_blocked_duplicate_unchecked(window):
    dialog=ImportGamesDialog(window.settings,window.games,window)
    records=[(RomLibraryEntry('Covered','CDI','covered.cdi'),''),(RomLibraryEntry('New','GDI','new'),''),(RomLibraryEntry('Broken','GDI','broken'),'missing track')]
    dialog.received(records)
    assert dialog.checked==[False,True,False]
    assert not dialog.table.cellWidget(2,0).isEnabled()
    dialog.select_all();assert dialog.checked==[True,True,False]
    emitted=[];dialog.selected.connect(emitted.extend);dialog.accept_selection()
    assert [item.name for item in emitted]==['Covered','New']


@pytest.mark.parametrize('language',['en','es'])
def test_import_feedback_formats_actual_detected_and_selected_counts(window,language):
    set_language(language)
    dialog=ImportGamesDialog(window.settings,window.games,window)
    dialog.received([(RomLibraryEntry('New','CDI','new.cdi'),''),(RomLibraryEntry('Covered','CDI','covered.cdi'),'')])
    assert '{' not in dialog.feedback.text()
    assert dialog.feedback.text()==catalog.tr('detected_games',count=2,selected=1)
    dialog.toggle(0,False)
    assert dialog.feedback.text()==catalog.tr('detected_games',count=2,selected=0)
    dialog.reject();set_language('es')


def test_import_cannot_accept_or_enable_prepare_while_inspection_runs(window,monkeypatch):
    import time
    from openmenu_gdemu_manager.ui.v2 import import_games
    dialog=ImportGamesDialog(window.settings,window.games,window)
    dialog.received([(RomLibraryEntry('Ready','CDI','ready.cdi'),'')])
    def slow(worker):
        time.sleep(.15);worker.finished.emit([])
    monkeypatch.setattr(import_games.InspectWorker,'run',slow)
    emitted=[];dialog.selected.connect(emitted.extend)
    dialog.inspect_paths(['unused'])
    dialog.toggle(0,True);dialog.accept_selection()
    assert not emitted and not dialog.prepare.isEnabled() and not dialog.table.isEnabled()
    assert dialog.scan_thread in window.cover_jobs
    for _ in range(100):
        QTest.qWait(10)
        if dialog.scan_thread is None:break
    assert dialog.scan_thread is None and dialog.prepare.isEnabled() and dialog.table.isEnabled()
    dialog.accept_selection();assert [entry.name for entry in emitted]==['Ready']


def test_save_does_not_auto_accept_bulk_proposals(window,monkeypatch):
    candidate=Candidate('test','Proposal',99)
    window.bulk_proposals={3:BulkProposal(3,candidate,Image.new('RGB',(512,512)),status='seleccionada')}
    assert not window.has_pending_changes()
    called=[];monkeypatch.setattr(window,'save_bulk_proposals',lambda **kw:called.append('unexpected'))
    window.save_changes_to_sd(confirm=False)
    assert called==[] and not window.games[1].selected_image


@pytest.mark.parametrize('action',['discard','keep'])
def test_cancelled_cover_review_cannot_leave_hidden_selection(window,monkeypatch,action):
    import copy
    from PySide6.QtWidgets import QDialog
    from openmenu_gdemu_manager.ui.v2 import main_window as v2
    game=window.games[0];store=window.cover_host.store;view=store.view(game)
    key=store.add_candidate(view,Candidate('test','Blue',99),Image.new('RGB',(512,512),'blue'))
    store.choose(view,key)
    before=copy.deepcopy(game.__dict__);state=copy.deepcopy(window.state)
    persisted=[];workers=[]
    monkeypatch.setattr(window,'_persist_cover_selection',lambda *a,**kw:persisted.append(a))
    monkeypatch.setattr(v2.ConfirmApplyDialog,'exec',lambda self:QDialog.DialogCode.Rejected)
    window.save_changes_to_sd()
    assert not persisted and game.__dict__==before and window.state==state
    assert view.choice==key
    if action=='discard':store.discard(view)
    else:assert store.choose(view,view.cover)=='kept'
    assert not window.has_pending_changes()
    monkeypatch.setattr(legacy,'update_game_state',lambda *a:None)
    window.save_game_name(window.games[1],'Another name')
    monkeypatch.setattr(window,'start_busy',lambda *a:None)
    monkeypatch.setattr(window,'_start_worker',lambda worker,*a,**kw:workers.append(worker))
    window.save_changes_to_sd(confirm=False)
    assert not persisted and not game.selected_image and len(workers)==1


def test_cover_materialization_occurs_only_after_accepted_review(window,monkeypatch):
    from PySide6.QtWidgets import QDialog
    from openmenu_gdemu_manager.ui.v2 import main_window as v2
    store=window.cover_host.store;view=store.view(window.games[1]);events=[]
    key=store.add_candidate(view,Candidate('test','Blue',99),Image.new('RGB',(512,512),'blue'))
    store.choose(view,key)
    def review(dialog):
        assert not view.real.selected_image
        events.append('review');return QDialog.DialogCode.Accepted
    monkeypatch.setattr(v2.ConfirmApplyDialog,'exec',review)
    monkeypatch.setattr(window,'_persist_cover_selection',lambda *a,**kw:events.append('persist'))
    monkeypatch.setattr(window,'start_busy',lambda *a:None)
    monkeypatch.setattr(window,'_start_worker',lambda *a,**kw:events.append('worker'))
    assert window.save_changes_to_sd() is True
    assert events==['review','persist','worker']


def test_search_worker_delivers_on_gui_thread(window,monkeypatch):
    from openmenu_gdemu_manager.ui import workers
    monkeypatch.setattr(workers,'find_candidates',lambda *a,**kw:[])
    monkeypatch.setattr(workers,'load_saved_candidates',lambda *a:[])
    monkeypatch.setattr(workers,'append_search_event_for_game',lambda *a:None)
    ws=ProductionWorkspace(window.cover_host,window.games[1],auto_search=False)
    observed=[];original=ws.search_finished
    ws.search_finished=lambda payload,token:(observed.append(QThread.currentThread() is QApplication.instance().thread()),original(payload,token))
    ws.search()
    for _ in range(200):
        QTest.qWait(10)
        if ws.search_thread is None:break
    assert observed==[True] and ws.search_thread is None
    ws.reject()


def test_all_actions_have_resources_and_translations():
    for action,spec in catalog.ACTIONS.items():
        assert (catalog.REFERENCE/'icons'/f"{spec['icon']}.svg").is_file()
        for language in ('en','es'):assert 'v2.action.'+action in load_internal_language(language).strings
    for language in ('en','es'):
        assert 'slot_recovery.revert_in_progress' in load_internal_language(language).strings


def test_original_functions_remain_available(window):
    for name in ('force_backup_current_sd','open_provider_settings','export_reports','open_setup_wizard','check_for_updates','save_bulk_proposals','rebuild_templates_menu','rebuild_language_menu'):
        assert callable(getattr(window,name))


def test_discard_restores_name_state_without_deleting_history(window,monkeypatch):
    from openmenu_gdemu_manager.config import state
    monkeypatch.setattr(state,'flush_state',lambda *args:None)
    monkeypatch.setattr(legacy,'update_game_state',lambda *args:None)
    game=window.games[1];window.save_game_name(game,'Edited')
    window.discard_pending_changes()
    assert game.name=='Missing' and not window.has_pending_changes()


def test_discard_restores_bulk_cover_after_sd_save_failure(window,monkeypatch,tmp_path):
    from openmenu_gdemu_manager.core.image_quality import analyze_image
    from openmenu_gdemu_manager.config import state
    monkeypatch.setattr(state,'flush_state',lambda *a:None)
    monkeypatch.setattr(legacy,'update_game_state',lambda *a:None)
    monkeypatch.setattr(legacy,'export_reports',lambda *a:None)
    monkeypatch.setattr(window,'show_error',lambda *a:None)
    game=window.games[1]
    window.apply_after_bulk_save=False
    path=tmp_path/'bulk.png';Image.new('RGB',(512,512),'blue').save(path)
    result={'slot':game.slot,'status':'seleccionada','normalized':str(path),'original':str(path),'preview':str(path),'source':'test','score':99,'quality':analyze_image(Image.open(path))}
    window._finish_save_bulk([result]);window.save_error('synthetic save failure')
    assert game.selected_image and window.has_pending_changes()
    window.discard_pending_changes()
    assert not game.selected_image and game.has_placeholder_cover and not window.has_pending_changes()


def test_failed_slot_transaction_disables_v2_writes_until_recovery(window,monkeypatch):
    from openmenu_gdemu_manager.services.sd_slot_transaction import SdSlotTransactionService
    SdSlotTransactionService(window.root_path,'failed')._write_state('failed')
    monkeypatch.setattr(window,'show_error',lambda *a:None)
    window.save_error('failed transaction')
    assert not window.write_allowed and window.read_only_reason
    assert not window.add_game_button.isEnabled() and not window.save_changes_button.isEnabled()


def test_identical_cover_kept_and_tonal_variant_is_distinct(window):
    game=window.games[0];store=window.cover_host.store;view=store.view(game)
    same=store.add_candidate(view,Candidate('test','Same',90),Image.open(game.current_cover).convert('RGB'))
    assert store.choose(view,same)=='kept'
    other=store.add_candidate(view,Candidate('test','Other',90),Image.new('RGB',(512,510),(250,150,10)))
    assert store.choose(view,other)=='chosen'


def test_search_web_preserves_configured_templates(window,monkeypatch):
    from openmenu_gdemu_manager.ui.v2 import bridge
    monkeypatch.setattr(bridge,'web_search_templates',lambda _:[{'name':'Custom','url':'https://example.test/?q={raw_query}&id={product_id}'}])
    ws=ProductionWorkspace(window.cover_host,window.games[0],auto_search=False)
    ws.web_menu()
    assert ws.web_popup.actions()[0].text()=='Custom'
    ws.web_popup.close();ws.reject()


def test_destination_uses_real_diagnostic_values(window):
    from openmenu_gdemu_manager.dreamcast.storage_diagnostics import StorageDiagnostic,RouteSummary
    summary=RouteSummary(window.root_path,filesystem='FAT32',free_bytes=24*1024**3)
    window.diagnostic=StorageDiagnostic(window.root_path,'gdemu_structure','ok','openmenu_compatible',True,True,summary=summary)
    window._refresh_controls()
    assert 'FAT32' in window.destination.destination_subtitle and '24.0' in window.destination.destination_subtitle
    assert '{' not in window.destination.destination_subtitle


def test_worker_rescan_waits_for_thread_cleanup(window,monkeypatch):
    running=[True];called=[]
    monkeypatch.setattr(window,'operation_running',lambda:running[0])
    monkeypatch.setattr(legacy.MainWindow,'start_scan',lambda self:called.append('scan'))
    window.start_scan();assert not called
    running[0]=False;window.refresh_after_worker()
    assert called==['scan'] and not window._rescan_after_worker


def test_old_icon_only_setting_cannot_clip_v2_labels(window):
    window.toggle_bulk_mode();QTest.qWait(30)
    for button in (window.add_game_button,window.save_changes_button,window.bulk_mode_button,window.bulk_button):
        assert not button.property('iconOnly')
        assert button.width()>=button.fontMetrics().horizontalAdvance(button.text())+button.iconSize().width()+12
