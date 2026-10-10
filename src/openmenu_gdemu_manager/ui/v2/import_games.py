"""Real file/folder inspection with explicit, reversible import selection."""
import logging
from pathlib import Path
from ...app.logger import logged_operation
from PySide6.QtCore import Qt,Signal,QObject,Slot
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QFileDialog,QTableWidget,QTableWidgetItem,QHeaderView,QMessageBox
from ...core.models import RomLibraryEntry
from ...dreamcast.rom_library import inspect_source,is_gdemu_menu_slot
from ...dreamcast.image_integrity import validate_source
from ...config.settings import supported_media_types
from ..workers import start_worker
from .design import Button,SelectionCheck,label
from .catalog import tr


log = logging.getLogger(__name__)


class InspectWorker(QObject):
    finished=Signal(object);error=Signal(str)
    def __init__(self,paths,supported):super().__init__();self.paths=paths;self.supported=supported
    @logged_operation("inspect_games")
    def run(self):
        try:
            results={}
            for path in self.paths:
                path=Path(path)
                sources=[path] if path.is_file() else [p for p in path.rglob('*') if p.suffix.lower() in ('.gdi','.cdi')]
                for source in sources:
                    if is_gdemu_menu_slot(source):continue
                    try:
                        entry=inspect_source(source,self.supported)
                        if entry is None:continue
                        reason=''
                        try:validate_source(entry.source_path)
                        except ValueError as exc:
                            log.warning("Source rejected: path=%s reason=%s", entry.source_path, exc)
                            reason=str(exc)
                        results.setdefault(entry.source_path.casefold(),(entry,reason))
                    except (OSError,ValueError) as exc:
                        log.warning("Source inspection failed: path=%s", source, exc_info=True)
                        entry=RomLibraryEntry(name=source.parent.name,media_type=source.suffix[1:].upper(),source_path=str(source))
                        results.setdefault(str(source).casefold(),(entry,str(exc)))
            self.finished.emit(list(results.values()))
        except Exception as exc:
            log.exception("Source inspection failed")
            self.error.emit(str(exc))


class ImportGamesDialog(QDialog):
    selected=Signal(object)
    def __init__(self,settings,games,parent=None):
        super().__init__(parent)
        self.settings,self.games=settings,games
        self.entries=[];self.errors=[];self.checked=[];self.scan_thread=None;self.scan_worker=None
        self._inspecting=False
        self._inspection_error=''
        self.resize(960,620);self.setWindowTitle(tr('add_title'))
        root=QVBoxLayout(self);root.setContentsMargins(20,16,20,16)
        root.addWidget(label(tr('add_title'),heading=True))
        root.addWidget(label(tr('choose_source'),muted=True,wrap=True))
        sources=QHBoxLayout()
        self.files=Button('game_files',self.pick_files);self.folder=Button('game_folder',self.pick_folder)
        sources.addWidget(self.files);sources.addWidget(self.folder);sources.addStretch();root.addLayout(sources)
        self.all=SelectionCheck(tr('all'));self.all.clicked.connect(self.select_all);root.addWidget(self.all)
        self.table=QTableWidget(0,5)
        self.table.setHorizontalHeaderLabels(['',tr('game'),tr('source_path'),tr('format'),tr('status')])
        self.table.verticalHeader().hide();self.table.verticalHeader().setDefaultSectionSize(68)
        self.table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0,38);self.table.setColumnWidth(3,90);self.table.setColumnWidth(4,190)
        self.table.cellClicked.connect(self.row_clicked);root.addWidget(self.table,1)
        self.feedback=label(tr('choose_source'),muted=True,wrap=True);root.addWidget(self.feedback)
        root.addWidget(label(tr('prepare_real_hint'),muted=True,wrap=True))
        bottom=QHBoxLayout();bottom.addStretch()
        self.cancel=Button('cancel',self.reject);self.prepare=Button('add',self.accept_selection,text=tr('prepare_games'))
        self.prepare.setEnabled(False);bottom.addWidget(self.cancel);bottom.addWidget(self.prepare);root.addLayout(bottom)

    def pick_files(self):
        files,_=QFileDialog.getOpenFileNames(self,tr('choose_source'),'','Dreamcast (*.gdi *.cdi)')
        if files:self.inspect_paths(files)

    def pick_folder(self):
        folder=QFileDialog.getExistingDirectory(self,tr('choose_source'))
        if folder:self.inspect_paths([folder])

    def inspect_paths(self,paths):
        if self.scan_thread is not None:return
        self._inspecting=True
        self._inspection_error=''
        self.files.setEnabled(False);self.folder.setEnabled(False);self.prepare.setEnabled(False)
        self.table.setEnabled(False);self.all.setEnabled(False)
        self.feedback.setText(tr('source_scanning'))
        start_worker(InspectWorker(paths,supported_media_types(self.settings)),'scan_thread','scan_worker',self,self.received,self.failed)
        self.scan_thread.finished.connect(self.inspection_finished)
        parent=self.parentWidget()
        if parent is not None and hasattr(parent,'cover_jobs'):parent.cover_jobs.append(self.scan_thread)

    @Slot()
    def inspection_finished(self):
        self._inspecting=False
        self.files.setEnabled(True);self.folder.setEnabled(True);self.table.setEnabled(True)
        self.sync()
        if self._inspection_error:self.feedback.setText(tr('read_failed',reason=self._inspection_error))

    def received(self,records):
        known={entry.source_path.casefold() for entry in self.entries}
        for entry,error in records:
            if entry.source_path.casefold() in known:continue
            known.add(entry.source_path.casefold())
            entry.existing_match=any(entry.name.casefold().strip()==g.name.casefold().strip() or bool(entry.product_id) and entry.product_id==g.product_id for g in self.games)
            self.entries.append(entry);self.errors.append(error);self.checked.append(not error and not entry.existing_match)
        self.render()

    def failed(self,message):
        self._inspection_error=message
        self.feedback.setText(tr('read_failed',reason=message))

    def render(self):
        self.table.setRowCount(len(self.entries))
        for row,entry in enumerate(self.entries):
            check=SelectionCheck(name=entry.name);check.setChecked(self.checked[row]);check.setEnabled(not self.errors[row]);check.clicked.connect(lambda value,r=row:self.toggle(r,value))
            self.table.setCellWidget(row,0,check)
            status=tr('verify_source') if self.errors[row] else tr('possible_duplicate') if entry.existing_match else tr('source_cdi_checked') if entry.media_type=='CDI' else tr('source_valid')
            for col,value in ((1,entry.name),(2,entry.source_path),(3,entry.media_type),(4,status)):
                item=QTableWidgetItem(value);item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable);item.setToolTip(self.errors[row] or (tr('source_cdi_scope') if entry.media_type=='CDI' and col==4 else value));self.table.setItem(row,col,item)
        self.sync()

    def toggle(self,row,value):self.checked[row]=bool(value);self.sync()
    def row_clicked(self,row,col):
        if col!=0 and not self.errors[row]:
            self.checked[row]=not self.checked[row];self.table.cellWidget(row,0).setChecked(self.checked[row]);self.sync()
    def select_all(self):
        targets=[i for i,error in enumerate(self.errors) if not error]
        select=not all(self.checked[i] for i in targets)
        for i in targets:self.checked[i]=select;self.table.cellWidget(i,0).setChecked(select)
        self.sync()
    def sync(self):
        count=sum(self.checked);targets=[i for i,error in enumerate(self.errors) if not error]
        self.all.setCheckState(Qt.CheckState.Checked if targets and all(self.checked[i] for i in targets) else Qt.CheckState.PartiallyChecked if count else Qt.CheckState.Unchecked)
        self.all.setEnabled(bool(targets) and not self._inspecting);self.prepare.setEnabled(bool(count) and not self._inspecting)
        if not self._inspecting:self.feedback.setText(tr('detected_games',count=len(self.entries),selected=count))
    def accept_selection(self):
        if self._inspecting or self.scan_thread is not None:return
        entries=[entry for i,entry in enumerate(self.entries) if self.checked[i] and not self.errors[i]]
        if entries:self.selected.emit(entries);self.accept()
    def reject(self):
        if self.scan_thread is not None:QMessageBox.information(self,self.windowTitle(),tr('close_busy'));return
        super().reject()
    def closeEvent(self,event):
        if self.scan_thread is not None:event.ignore()
        else:super().closeEvent(event)
