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
    for card in ws.gallery.cards:
        assert card.choose.geometry().bottom()<=card.height()
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


def test_save_does_not_auto_accept_bulk_proposals(window,monkeypatch):
    candidate=Candidate('test','Proposal',99)
    window.bulk_proposals={3:BulkProposal(3,candidate,Image.new('RGB',(512,512)),status='seleccionada')}
    assert not window.has_pending_changes()
    called=[];monkeypatch.setattr(window,'save_bulk_proposals',lambda **kw:called.append('unexpected'))
    window.save_changes_to_sd(confirm=False)
    assert called==[] and not window.games[1].selected_image


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
