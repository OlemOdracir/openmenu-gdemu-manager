"""Connect approved cover workspace to original search/persistence services."""
import logging
from pathlib import Path
from ...app.logger import logged_operation
from PIL import Image
from PySide6.QtCore import QObject,Signal,QTimer,Qt,Slot,QUrl
from PySide6.QtGui import QPixmap,QDesktopServices
from PySide6.QtWidgets import QWidget,QDialog,QVBoxLayout,QHBoxLayout,QScrollArea,QMessageBox,QComboBox,QMenu
from ...core.models import Candidate,VALID_STATES
from ...core.image_quality import normalize_cover,analyze_image
from ...covers.search import load_candidate_image
from ...services.cover_library import load_saved_candidates
from ...i18n import tr as app_tr,translate_status
from ...config.settings import load_settings,web_search_templates
from ...config.paths import INBOX_ORIGINALS_DIR
from ..workers import SearchWorker,start_worker
from ..image_qt import pil_to_pixmap
from . import catalog
from .catalog import tr,variant
from .design import Button,label,box
from .covers import CoverWorkspace
from .state import CoverStore


log = logging.getLogger(__name__)


class CoverSearchWorker(QObject):
    finished=Signal(object)
    error=Signal(str)

    def __init__(self, game, query, write_allowed):
        super().__init__()
        self.game,self.query,self.write_allowed=game,query,write_allowed
        self.cancelled=False

    def cancel(self):self.cancelled=True

    @logged_operation("search_covers")
    def run(self):
        log.info("Cover search started: game=%s query=%s", getattr(self.game,"name",""), self.query)
        worker=SearchWorker(self.game,self.query,write_allowed=self.write_allowed)
        worker.finished.connect(self.prepare)
        worker.error.connect(self.error.emit)
        worker.run()

    @logged_operation("prepare_cover_images")
    def prepare(self, payload):
        prepared=[]
        for candidate in payload.get('candidates',[]):
            if self.cancelled:break
            try:
                image=load_candidate_image(candidate)
                report=analyze_image(image)
                candidate.width,candidate.height=image.size
                candidate.quality_label,candidate.quality_score=report.label,report.score
                prepared.append((candidate,image,''))
            except Exception as exc:
                log.exception("Cover preparation failed: game=%s query=%s provider=%s image=%s",
                              getattr(self.game,"name",""), self.query, candidate.source, candidate.local_path or candidate.url)
                prepared.append((candidate,None,str(exc)))
        self.finished.emit({'items':prepared,'query':self.query,'cancelled':self.cancelled})


class CoverHost(QWidget):
    """Small UI adapter, without a second application controller or simulation."""
    def __init__(self, window):
        super().__init__(window)
        self.window=window
        self.store=CoverStore(window)
        self.hide()

    def refresh_collection(self):
        self.window.apply_filters()

    def confirm(self,title,body,callback,parent=None,**kwargs):
        dialog=QMessageBox(parent or self.window)
        dialog.setWindowTitle(title)
        dialog.setText(body)
        accept=dialog.addButton(catalog.action_label('select'),QMessageBox.ButtonRole.AcceptRole)
        dialog.addButton(catalog.action_label('cancel'),QMessageBox.ButtonRole.RejectRole)
        dialog.exec()
        if dialog.clickedButton() is accept:callback()

    def show_save(self,parent=None):
        try:started=self.window.save_changes_to_sd()
        except Exception as exc:
            self.window.show_error(str(exc));return
        if isinstance(parent,CoverWorkspace):
            if started:parent.accept()
            else:parent.refresh()

    def show_info(self,game,parent=None,image_key=None):
        real=game.real
        dialog=QDialog(parent or self.window)
        dialog.resize(640,520)
        dialog.setWindowTitle(catalog.action_label('image_info' if image_key else 'info'))
        root=QVBoxLayout(dialog)
        root.setContentsMargins(20,20,20,20)
        root.addWidget(label(dialog.windowTitle(),heading=True))
        scroll=QScrollArea()
        scroll.setWidgetResizable(True)
        content,listing=box(spacing=6)
        if image_key:
            item=self.store.images[image_key]
            candidate=self.store.candidate_objects.get(image_key)
            match=tr('product_match') if candidate and candidate.product_match else tr('alias_match') if candidate and candidate.alias_match else tr('edition_warning') if item.get('weak_match') else tr('local_match') if item.get('variant_index') else tr('match_sample')
            values=[('game',item['title']),('available_design',variant(item)),('region',item['region'] or tr('unidentified')),
                ('resolution',f"{item['width']} × {item['height']} px"),('quality',tr('cover_quality',label=item.get('quality_label',''),score=item.get('quality_score',0))),
                ('match',match),('provider',item.get('provider','')),('available_file',item.get('sourceFile','')),
                ('sources',' · '.join(item.get('duplicate_sources',[])) or tr('unavailable')),('original_image',tr('original_note'))]
        else:
            pending=[tr(key) for condition,key in ((real.pending_add,'new_pending'),(real.pending_delete,'remove_pending'),(bool(game.choice) or real.save_status=='pendiente_guardar','pending'),(game.title!=game.original,'name_pending')) if condition]
            values=[('openmenu_name',game.title),('saved_name',game.original),('internal_name',real.internal_name or tr('unavailable')),
                ('position',f'{real.slot:03d}'),('region',real.region or tr('unidentified')),('disc_id',real.product_id if not real.product_id.startswith('SLOT') else tr('not_disc_id')),
                ('technical_reference',real.product_id),('status',' · '.join(pending) or translate_status(real.status)),
                ('source_path',real.source_path or str(real.folder or '')),('format',real.media_type),('quality',real.quality_label or tr('not_analyzed'))]
            for key in ('disc','vga','version','date'):
                listing.addWidget(label(tr(key),muted=True))
                listing.addWidget(label(str(getattr(real,key,'')) or tr('unavailable'),wrap=True))
            for code in real.consistency_warnings:
                listing.addWidget(label(app_tr('scan_repair.warning.'+code),tone='warning',wrap=True))
        for key,value in values:
            listing.addWidget(label(tr(key),muted=True))
            listing.addWidget(label(value or tr('unavailable'),wrap=True))
        if image_key and candidate:
            def open_source():
                url=candidate.source_url or candidate.url
                if url and QUrl(url).scheme()=='https':QDesktopServices.openUrl(QUrl(url))
                elif candidate.local_path:self.window.open_path(Path(candidate.local_path).parent)
            listing.addWidget(Button('web',open_source,text=tr('open_source')))
        if not image_key:
            status=QComboBox()
            for key in sorted(VALID_STATES):status.addItem(translate_status(key),key)
            status.setCurrentIndex(max(0,status.findData(real.status)))
            status.setEnabled(self.store.writable)
            status.currentIndexChanged.connect(lambda:self.window.set_status(real,status.currentData()))
            listing.addWidget(label(tr('cover_status'),muted=True))
            listing.addWidget(status)
            folder=Button('browse',lambda:self.window.open_path(real.folder),text=tr('open_folder'))
            folder.setEnabled(bool(real.folder))
            listing.addWidget(folder)
            undo=Button('undo_name',lambda:(self.store.rename(game,game.original),dialog.accept()))
            undo.setEnabled(self.store.writable)
            listing.addWidget(undo)
            remove=Button('remove',lambda:(dialog.accept(),self.window.toggle_delete_game(real)),text=tr('undo_remove') if real.pending_delete else None)
            remove.setEnabled(self.store.writable)
            listing.addWidget(remove)
            history=load_saved_candidates(real)
            if history:
                listing.addWidget(label(tr('history_real'),title=True))
                for candidate in history:
                    key=self.store.add_candidate(game,candidate)
                    listing.addWidget(Button('inspect',lambda _,k=key:(dialog.accept(),self.window.inspect_image(real,k,parent)),text=candidate.title))
        listing.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll,1)
        root.addWidget(Button('close',dialog.reject),0,Qt.AlignmentFlag.AlignRight)
        dialog.exec()


class ProductionWorkspace(CoverWorkspace):
    def __init__(self,host,real,*,auto_search=True):
        host.resize(host.window.size())
        self.real=real
        self.search_thread=None
        self.search_worker=None
        self.search_jobs=[]
        self.retry_thread=None
        self.retry_worker=None
        super().__init__(host,host.store.view(real))
        self.setWindowIcon(host.window.windowIcon())
        self.save.setEnabled(host.window.write_allowed and host.window.has_pending_changes())
        if auto_search:QTimer.singleShot(0,self.search)

    def pixmap(self,key):
        if not key:return QPixmap()
        if key not in self.cache:
            try:
                image=self.store.image(key)
                self.cache[key]=pil_to_pixmap(image,image.size)
                self.store.images[key]['failed']=False
            except (OSError,ValueError,KeyError):
                self.store.images[key]['failed']=True
                self.cache[key]=QPixmap()
        return self.cache[key]

    def normalized_pixmap(self,key):
        image=normalize_cover(self.store.image(key))
        return pil_to_pixmap(image,image.size)

    def search(self):
        query=self.session.query.strip()
        if not query:self.message(tr('empty_query'));return
        if self.search_thread is not None and self.search_thread.isRunning():return
        self.search_request+=1
        token=self.search_request
        self.gallery.search.setEnabled(False)
        self.gallery.search.setText(tr('searching'))
        self.message(tr('search_progress'))
        worker=CoverSearchWorker(self.real,query,self.owner.window.write_allowed)
        self.active_token=token
        start_worker(worker,'search_thread','search_worker',self,
            on_finished=self.receive_search,
            on_error=self.receive_error)
        self.search_jobs.append(self.search_thread)
        # Keep running jobs alive after closing the detail, without late UI work.
        self.owner.window.cover_jobs.append(self.search_thread)

    def web_menu(self):
        from urllib.parse import quote_plus
        menu=QMenu(self)
        for template in web_search_templates(load_settings()):
            expanded=template['url'].format(query=quote_plus(self.session.query+' Dreamcast cover art'),raw_query=quote_plus(self.session.query),product_id=quote_plus(self.game.product or self.session.query))
            if QUrl(expanded).scheme()=='https':menu.addAction(template['name'],lambda u=expanded:QDesktopServices.openUrl(QUrl(u)))
        if self.game.product and not self.game.product.startswith('SLOT'):
            url='https://www.google.com/search?tbm=isch&q='+quote_plus(self.game.product+' Dreamcast cover')
            menu.addAction(self.game.product,lambda:QDesktopServices.openUrl(QUrl(url)))
        menu.addSeparator()
        def open_library():
            INBOX_ORIGINALS_DIR.mkdir(parents=True,exist_ok=True)
            self.owner.window.open_path(INBOX_ORIGINALS_DIR)
        menu.addAction(tr('open_cover_library'),open_library)
        menu.popup(self.gallery.web.mapToGlobal(self.gallery.web.rect().bottomLeft()))
        self.web_popup=menu

    def retry_image(self,key):
        if self.retry_thread is not None:return
        candidate=self.store.candidate_objects.get(key)
        if candidate is None:return super().retry_image(key)
        self.retry_key=key
        worker=RetryImageWorker(candidate)
        start_worker(worker,'retry_thread','retry_worker',self,self.retry_finished,self.retry_failed)
        self.owner.window.cover_jobs.append(self.retry_thread)
        self.message(tr('search_progress'))

    @Slot(object)
    def retry_finished(self,payload):
        if self._closed:return
        candidate,image=payload
        self.store.add_candidate(self.game,candidate,image,key=self.retry_key)
        self.cache.pop(self.retry_key,None)
        super().retry_image(self.retry_key)

    @Slot(str)
    def retry_failed(self,message):
        if not self._closed:self.message(tr('read_failed',reason=message))

    @Slot(object)
    def receive_search(self,payload):self.search_finished(payload,self.active_token)

    @Slot(str)
    def receive_error(self,message):self.search_failed(message,self.active_token)

    def search_finished(self,payload,token):
        if self._closed or token!=self.search_request:return
        self.gallery.search.setEnabled(True)
        self.gallery.search.setText(catalog.action_label('search'))
        if payload.get('cancelled'):self.message(tr('search_cancelled'));return
        keys=[]
        for candidate,image,error in payload['items']:
            key=self.store.add_candidate(self.game,candidate,image)
            if error:self.store.images[key]['failed']=True
            keys.append(key)
        self.session.results=keys
        self.session.result_query=payload['query']
        self.session.page=1
        self.results()
        self.message(tr('gallery_hint' if keys else 'no_results_hint'))

    def search_failed(self,message,token):
        if self._closed or token!=self.search_request:return
        self.gallery.search.setEnabled(True)
        self.gallery.search.setText(catalog.action_label('search'))
        self.message(tr('read_failed',reason=message))

    def refresh(self):
        super().refresh()
        self.save.setEnabled(self.owner.window.write_allowed and self.owner.window.has_pending_changes())

    def invalidate_requests(self,*args):
        super().invalidate_requests(*args)
        if self.search_worker is not None:self.search_worker.cancel()

    def import_paths(self,paths):
        super().import_paths(paths)
        for key in self.session.local:
            if key not in self.store.candidate_objects:
                item=self.store.images[key]
                self.store.candidate_objects[key]=Candidate('local',item['title'],100,local_path=item['local_path'])
                from ...core.dedupe import exact_image_hash
                item['contentId']=exact_image_hash(self.store.image(key))


class RetryImageWorker(QObject):
    finished=Signal(object);error=Signal(str)
    def __init__(self,candidate):super().__init__();self.candidate=candidate
    @logged_operation("retry_cover_image")
    def run(self):
        try:self.finished.emit((self.candidate,load_candidate_image(self.candidate)))
        except Exception as exc:
            log.exception("Cover retry failed: provider=%s image=%s", self.candidate.source, self.candidate.local_path or self.candidate.url)
            self.error.emit(str(exc))
