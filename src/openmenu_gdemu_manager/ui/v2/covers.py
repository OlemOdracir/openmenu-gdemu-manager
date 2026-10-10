from __future__ import annotations

import hashlib
from math import ceil
from pathlib import Path
from urllib.parse import urlencode

from PySide6.QtCore import Qt, QTimer, QSize, QPointF, Signal, QUrl
from PySide6.QtGui import QPixmap, QDesktopServices, QPainter, QColor
from PySide6.QtWidgets import QApplication, QDialog, QWidget, QFrame, QVBoxLayout, QHBoxLayout, QGridLayout, QScrollArea, QLineEdit, QStackedWidget, QSizePolicy, QGraphicsView, QGraphicsScene, QComboBox, QMenu, QLayout

from . import catalog
from .catalog import tr, variant
from .design import Button, ImageTile, label, box, repolish, colors, clearable_edit


class Card(QFrame):
    def __init__(self, workspace, key):
        super().__init__()
        self.key = key
        self.setObjectName("Card")
        self.setProperty("chosen", workspace.game.choice == key)
        self.setMinimumHeight(152)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        item = workspace.store.images[key]
        grid = QGridLayout(self)
        grid.setContentsMargins(8,8,8,8)
        grid.setSpacing(4)
        grid.setColumnStretch(0, 2)
        grid.setColumnStretch(1, 3)
        grid.setRowStretch(0, 1)
        self.image = ImageTile(workspace.pixmap(key), tr("inspection")+" "+variant(item))
        self.image.setMaximumWidth(160)
        self.image.clicked.connect(lambda: workspace.inspect(key))
        grid.addWidget(self.image, 0, 0)
        caption, content = box(spacing=3)
        title = label(item["title"], title=True, wrap=True)
        title.setMaximumHeight(42)
        title.setToolTip(item["title"])
        content.addWidget(title)
        v = label(variant(item), muted=True, wrap=True)
        v.setMaximumHeight(32)
        v.setToolTip(variant(item))
        content.addWidget(v)
        content.addWidget(label(f"{item.get('region') or tr('unidentified')} · {item['width']} × {item['height']} px", muted=True, wrap=True))
        content.addStretch()
        mark = "image_error" if item.get('failed') else "chosen_card" if workspace.game.choice == key else "current_cover" if workspace.game.cover == key else "finalist_a" if workspace.session.a == key else "edition_warning" if item.get('weak_match') else "available_choice"
        content.addWidget(label(tr(mark), muted=True, tone="pending" if workspace.game.choice == key else None, wrap=True))
        grid.addWidget(caption, 0, 1)
        actions, row = box(False, spacing=4)
        row.addStretch()
        self.enlarge = Button("inspect", lambda: workspace.inspect(key), compact=True)
        self.compare = Button("compare", lambda: workspace.compare(key), text=tr("marked_a") if workspace.session.a == key else None, compact=True)
        self.compare.setEnabled(not item.get('failed'))
        action = "keep" if workspace.game.cover == key else "select"
        self.choose = Button(action, lambda: workspace.choose(key), compact=True)
        self.choose.setEnabled(workspace.store.writable and not item.get("failed"))
        for b in (self.enlarge, self.compare, self.choose):
            row.addWidget(b)
        grid.addWidget(actions, 1, 0, 1, 2)


class Gallery(QWidget):
    def __init__(self, workspace):
        super().__init__()
        self.workspace = workspace
        self.cards = []
        self.columns = 3
        root = QVBoxLayout(self)
        root.setContentsMargins(8,8,8,8)
        root.setSpacing(4)
        query = QHBoxLayout()
        query.setSpacing(8)
        self.query = clearable_edit(workspace.session.query,tr('query_label'))
        self.query.setObjectName("cover_query")
        self.query.textChanged.connect(self.query_changed)
        self.query.returnPressed.connect(workspace.search)
        query.addWidget(self.query, 1)
        self.search = Button("search", workspace.search, compact=True)
        self.rename = Button("rename", workspace.rename, compact=True)
        self.local = Button("local_file", workspace.import_local, compact=True)
        self.web = Button("web", workspace.web_menu, compact=True)
        for b in (self.search, self.rename, self.local, self.web):
            query.addWidget(b)
        root.addLayout(query)
        self.hint = label(tr("name_hint"), muted=True)
        root.addWidget(self.hint)
        self.reference, ref = box(False, margins=4, name="Reference")
        self.current_image = ImageTile(workspace.pixmap(workspace.game.cover), tr("saved_cover"))
        self.current_image.setFixedSize(44, 44)
        self.current_image.setEnabled(bool(workspace.game.cover))
        self.current_image.clicked.connect(lambda: workspace.inspect(workspace.game.cover))
        ref.addWidget(self.current_image)
        current, cl = box(spacing=2)
        cl.addWidget(label(tr("saved_cover" if workspace.game.cover else "no_saved_cover"), title=True))
        cl.addWidget(label(tr("reference"), muted=True))
        ref.addWidget(current, 3)
        status, sl = box(spacing=2)
        self.choice_title = label("", title=True)
        self.choice_variant = label("", muted=True)
        sl.addWidget(self.choice_title)
        sl.addWidget(self.choice_variant)
        ref.addWidget(status, 5)
        self.discard = Button("discard", workspace.discard, compact=True)
        ref.addWidget(self.discard)
        self.info = Button("info", lambda: workspace.owner.show_info(workspace.game, workspace), compact=True)
        ref.addWidget(self.info)
        root.addWidget(self.reference)
        intro = QHBoxLayout()
        self.count = label("", title=True)
        intro.addWidget(self.count, 1)
        self.results_hint = label("", muted=True)
        intro.addWidget(self.results_hint, 1)
        root.addLayout(intro)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.scroll.setMinimumHeight(160)
        self.grid_widget = QWidget()
        self.grid_widget.setObjectName("Surface")
        self.grid = QGridLayout(self.grid_widget)
        self.grid.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        self.grid.setContentsMargins(0,0,0,0)
        self.grid.setSpacing(8)
        self.scroll.setWidget(self.grid_widget)
        root.addWidget(self.scroll, 1)
        pager = QHBoxLayout()
        self.page_label = label("", muted=True)
        pager.addWidget(self.page_label, 1)
        self.previous = Button("previous", lambda: self.page(-1), compact=True)
        self.next = Button("next", lambda: self.page(1), compact=True)
        pager.addWidget(self.previous)
        pager.addWidget(self.next)
        root.addLayout(pager)
        self.refresh()

    def query_changed(self, text):
        self.workspace.session.query = text
        self.rename.setEnabled(self.workspace.store.writable and bool(text.strip()) and text.strip() != self.workspace.game.title)

    def page(self, delta):
        self.workspace.session.page += delta
        self.refresh()
        (self.next if delta > 0 else self.previous).setFocus()

    def refresh(self):
        ws, game, s = self.workspace, self.workspace.game, self.workspace.session
        self.query_changed(s.query)
        self.current_image.pm = ws.pixmap(game.cover)
        self.current_image.setEnabled(bool(game.cover))
        self.current_image.update()
        key = game.choice or game.proposal
        self.choice_title.setText(tr("choice_pending" if game.choice else "proposal" if game.proposal else "no_choice"))
        self.choice_variant.setText(variant(ws.store.images[key]) if key else tr("explore"))
        self.discard.setVisible(bool(game.choice))
        self.discard.setEnabled(ws.store.writable)
        self.count.setText(tr("alternatives", count=len(ws.store.candidates(game))))
        self.results_hint.setText(tr("search_samples", query=s.result_query))
        self.results_hint.setToolTip(self.results_hint.text())
        self.populate()

    def populate(self):
        focus=self.focus_target()
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        # Reset stretches left by a different responsive arrangement.
        for i in range(6):
            self.grid.setRowStretch(i, 0)
            self.grid.setColumnStretch(i, 0)
        ws = self.workspace
        keys, pages = ws.store.page_keys(ws.game)
        self.cards = [Card(ws, key) for key in keys]
        if not self.cards:
            empty, layout = box(spacing=12)
            layout.addStretch()
            layout.addWidget(label(tr("no_results"), heading=True), 0, Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(label(tr("no_results_hint"), muted=True), 0, Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(Button("local_file", ws.import_local, compact=True), 0, Qt.AlignmentFlag.AlignCenter)
            layout.addStretch()
            self.grid.addWidget(empty, 0, 0)
            self.grid_widget.setMinimumHeight(0)
        else:
            rows = ceil(6 / self.columns)
            for idx, card in enumerate(self.cards):
                self.grid.addWidget(card, idx//self.columns, idx%self.columns)
                card.ensurePolished()
                card.setMinimumHeight(max(152,card.sizeHint().height()))
            for r in range(rows):
                self.grid.setRowStretch(r, 1)
            for c in range(self.columns):
                self.grid.setColumnStretch(c, 1)
            # Native Windows/DPI metrics can make a card taller than 152px.
            # Resolve its real minimum before scrolling/focus is positioned.
            self.grid.invalidate()
            self.grid.activate()
            self.grid_widget.setMinimumHeight(max(rows * 152 + (rows-1)*8,self.grid.minimumSize().height()))
            self.grid_widget.resize(self.grid_widget.width(),max(self.grid_widget.height(),self.grid_widget.minimumHeight()))
            self.grid.setGeometry(self.grid_widget.rect())
        total = len(ws.store.candidates(ws.game))
        self.page_label.setText(tr("pagination", start=(ws.session.page-1)*6+1 if total else 0, end=min(ws.session.page*6,total), total=total, page=ws.session.page, pages=pages))
        self.previous.setEnabled(ws.session.page > 1)
        self.next.setEnabled(ws.session.page < pages)
        self.scroll.verticalScrollBar().setValue(0)
        if focus:QTimer.singleShot(0,lambda target=focus:self.restore_focus(target))

    def focus_target(self):
        focused=QApplication.focusWidget()
        for card in self.cards:
            if focused is card.image:return (card.key,'image')
            for action,button in (('inspect',card.enlarge),('compare',card.compare),('select',card.choose)):
                if focused is button:return (card.key,action)
        return None

    def restore_focus(self,target):
        if not self.isVisible():return
        for card in self.cards:
            if card.key==target[0]:
                button={'image':card.image,'inspect':card.enlarge,'compare':card.compare,'select':card.choose}[target[1]]
                if button.isEnabled():button.setFocus();return
        self.query.setFocus()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        columns = 3 if self.width() >= 1000 else 2 if self.width() >= 700 else 1
        if columns != self.columns:
            self.columns = columns
            self.populate()


class ImageView(QGraphicsView):
    moved = Signal(object)

    def __init__(self, pixmap, name):
        super().__init__()
        self.setAccessibleName(name)
        self.source = pixmap
        self.normalized_source = None
        self.scene_ = QGraphicsScene(self)
        self.setScene(self.scene_)
        self.item = self.scene_.addPixmap(pixmap)
        if pixmap.isNull():self.scene_.addText(tr('image_error'))
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setRenderHint(__import__('PySide6.QtGui', fromlist=['QPainter']).QPainter.RenderHint.SmoothPixmapTransform)
        self.setBackgroundBrush(QColor(colors()['soft']))
        self.zoom = "fit"
        self.horizontalScrollBar().valueChanged.connect(lambda: self.moved.emit(self))
        self.verticalScrollBar().valueChanged.connect(lambda: self.moved.emit(self))

    def update_zoom(self, zoom, normalized=False):
        self.zoom = zoom
        pm=self.source
        if normalized:
            pm=self.normalized_source or self.source
        self.item.setPixmap(pm)
        self.scene_.setSceneRect(self.item.boundingRect())
        if zoom == "fit":
            self.fitInView(self.item, Qt.AspectRatioMode.KeepAspectRatio)
        else:
            self.resetTransform()
            self.scale(zoom/100, zoom/100)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.zoom == "fit":
            self.fitInView(self.item, Qt.AspectRatioMode.KeepAspectRatio)


class Viewer(QWidget):
    def __init__(self, ws, comparison=False):
        super().__init__()
        self.workspace = ws
        self.comparison = comparison
        self.zoom = "fit"
        self.normalized = False
        self.alternate = False
        self.alt_side = "A"
        self.syncing = False
        self.views = []
        self.panels = []
        root = QVBoxLayout(self)
        root.setContentsMargins(12,12,12,12)
        tools = QHBoxLayout()
        tools.setSpacing(4)
        for action, cb in (("fit",lambda:self.set_zoom("fit")), ("actual_size",lambda:self.set_zoom(100)), ("zoom_out",lambda:self.set_zoom(max(25,(100 if self.zoom=='fit' else self.zoom)-25)))):
            tools.addWidget(Button(action, cb, compact=True))
        self.zoom_label = label(tr("full_view"), muted=True)
        self.zoom_label.setMinimumWidth(85)
        tools.addWidget(self.zoom_label)
        tools.addWidget(Button("zoom_in",lambda:self.set_zoom(min(400,(100 if self.zoom=='fit' else self.zoom)+25)), compact=True))
        tools.addStretch()
        tools.addWidget(Button("image_source",lambda:self.set_mode(False),compact=True))
        tools.addWidget(Button("normalized",lambda:self.set_mode(True),compact=True))
        if comparison:
            tools.addWidget(Button("side",lambda:self.layout_mode(False),compact=True))
            tools.addWidget(Button("alternate",lambda:self.layout_mode(True),compact=True))
        root.addLayout(tools)
        self.toggle_bar, toggle = box(False)
        toggle.addWidget(Button("alternate",lambda:self.show_side("A"),text=tr("view_a"),compact=True))
        toggle.addWidget(Button("alternate",lambda:self.show_side("B"),text=tr("view_b"),compact=True))
        toggle.addStretch()
        self.toggle_bar.setVisible(False)
        root.addWidget(self.toggle_bar)
        area = QHBoxLayout()
        sides = [("A",ws.session.a),("B",ws.session.b)] if comparison else [("inspect",ws.session.inspected)]
        keys = list(dict.fromkeys(ws.store.candidates(ws.game)+[k for k in (ws.game.cover, ws.game.choice, ws.session.a, ws.session.b) if k]))
        for side, key in sides:
            pane, column = box()
            title = QHBoxLayout()
            title.addWidget(label(tr("inspection") if side=='inspect' else side, title=True))
            if comparison:
                combo = QComboBox()
                combo.setAccessibleName(tr("comparison")+" "+side)
                for candidate in keys:
                    item = ws.store.images[candidate]
                    combo.addItem(variant(item)+f" · {item.get('region','')} · {item['width']}×{item['height']}", candidate)
                combo.setCurrentIndex(keys.index(key))
                combo.currentIndexChanged.connect(lambda _, c=combo, side=side:self.change_finalist(side,c))
                title.addWidget(combo, 1)
            column.addLayout(title)
            view = ImageView(ws.pixmap(key), tr("inspection")+" "+side)
            if not ws.store.images[key].get('failed'):
                view.normalized_source=ws.normalized_pixmap(key)
            view.moved.connect(self.sync_pan)
            self.views.append(view)
            self.panels.append(pane)
            column.addWidget(view, 1)
            item=ws.store.images[key]
            self.quality_text=tr('image_error' if item.get('failed') else 'resolution_small' if min(item['width'],item['height'])<200 else 'resolution_low' if min(item['width'],item['height'])<240 else 'resolution_sufficient')
            self.meta = label(self.quality_text+' · '+tr("source_hint"), muted=True)
            self.meta.setProperty('quality_key',key)
            column.addWidget(self.meta)
            if comparison:
                actions = QHBoxLayout()
                actions.addWidget(Button("image_info", lambda _, k=key:ws.owner.show_info(ws.game,ws,k),compact=True))
                pick = Button("select",lambda _, k=key:ws.choose(k), text=tr("choose_a" if side=='A' else "choose_b"),compact=True)
                pick.setEnabled(ws.store.writable and not ws.store.images[key].get('failed'))
                actions.addWidget(pick)
                column.addLayout(actions)
            area.addWidget(pane, 1)
        if not comparison:
            item=ws.store.images[ws.session.inspected]
            aside, details=box(spacing=12)
            aside.setFixedWidth(230)
            details.addWidget(label(item['title'],heading=True,wrap=True))
            details.addWidget(label(variant(item),muted=True,wrap=True))
            details.addWidget(label(f"{item['width']} × {item['height']} px · {item.get('region') or tr('unidentified')}",muted=True,wrap=True))
            pick=Button('keep' if ws.game.cover==ws.session.inspected else 'select',lambda:ws.choose(ws.session.inspected),compact=True)
            pick.setEnabled(ws.store.writable and not item.get('failed'))
            details.addWidget(pick)
            compare=Button('compare',lambda:ws.compare(ws.session.inspected),text=tr('mark_compare'),compact=True)
            compare.setEnabled(not item.get('failed'))
            details.addWidget(compare)
            details.addWidget(Button('image_info',lambda:ws.owner.show_info(ws.game,ws,ws.session.inspected),compact=True))
            if item.get('failed'):details.addWidget(Button('retry',lambda:ws.retry_image(ws.session.inspected),compact=True))
            details.addWidget(Button('back',ws.results,text=tr('back_results'),compact=True))
            details.addWidget(label(tr('inspect_hint'),muted=True,wrap=True))
            details.addStretch()
            area.addWidget(aside)
        root.addLayout(area,1)
        bottom = QHBoxLayout()
        bottom.addWidget(label(tr("inspect_hint"),muted=True),1)
        if comparison:
            bottom.addWidget(Button("clear_pair",self.clear_pair,compact=True))
        if comparison:bottom.addWidget(Button("back",ws.results,text=tr("back_results"),compact=True))
        root.addLayout(bottom)
        QTimer.singleShot(0,lambda:self.set_zoom('fit'))

    def set_zoom(self, zoom):
        self.zoom = zoom
        self.syncing = True
        for view in self.views:
            view.update_zoom(zoom, self.normalized)
        self.syncing = False
        self.zoom_label.setText(tr("full_view") if zoom=='fit' else f"{zoom} %")

    def set_mode(self, normalized):
        self.normalized = normalized
        self.set_zoom(self.zoom)
        for panel in self.panels:
            # Metadata lives immediately below the image view.
            metadata=panel.layout().itemAt(2).widget()
            item=self.workspace.store.images[metadata.property('quality_key')]
            quality=tr('image_error' if item.get('failed') else 'resolution_small' if min(item['width'],item['height'])<200 else 'resolution_low' if min(item['width'],item['height'])<240 else 'resolution_sufficient')
            metadata.setText(quality+' · '+tr("normalized_hint" if normalized else "source_hint"))

    def layout_mode(self, alternate):
        self.alternate = alternate
        self.toggle_bar.setVisible(alternate)
        self.show_side(self.alt_side)

    def show_side(self, side):
        self.alt_side = side
        for i, panel in enumerate(self.panels):
            panel.setVisible(not self.alternate or i == (0 if side=='A' else 1))

    def sync_pan(self, source):
        if self.syncing or self.zoom == 'fit' or not self.comparison:
            return
        self.syncing = True
        rect = source.sceneRect()
        point = source.mapToScene(source.viewport().rect().center())
        x, y = point.x()/max(1,rect.width()), point.y()/max(1,rect.height())
        for view in self.views:
            if view is not source:
                target = view.sceneRect()
                view.centerOn(QPointF(x*target.width(),y*target.height()))
        self.syncing = False

    def change_finalist(self, side, combo):
        s, store = self.workspace.session, self.workspace.store
        key = combo.currentData()
        other = s.b if side=='A' else s.a
        if store.images[key].get('contentId',key) == store.images[other].get('contentId',other):
            combo.blockSignals(True)
            combo.setCurrentIndex(combo.findData(s.a if side=='A' else s.b))
            combo.blockSignals(False)
            self.workspace.message(tr("same_pair"))
            return
        if side=='A': s.a=key
        else: s.b=key
        self.workspace.show_viewer(True,self.snapshot())

    def snapshot(self):
        view=self.views[0]
        point=view.mapToScene(view.viewport().rect().center())
        rect=view.sceneRect()
        return {'zoom':self.zoom,'normalized':self.normalized,'alternate':self.alternate,'alt_side':self.alt_side,'pan':(point.x()/max(1,rect.width()),point.y()/max(1,rect.height()))}

    def restore(self,state):
        self.normalized=state['normalized']
        self.set_mode(self.normalized)
        self.set_zoom(state['zoom'])
        self.alt_side=state['alt_side']
        self.layout_mode(state['alternate'])
        self.syncing=True
        for view in self.views:
            rect=view.sceneRect()
            view.centerOn(state['pan'][0]*rect.width(),state['pan'][1]*rect.height())
        self.syncing=False

    def clear_pair(self):
        self.workspace.session.a = self.workspace.session.b = None
        self.workspace.results()


class CoverWorkspace(QDialog):
    def __init__(self, owner, game, inspect=False):
        super().__init__(owner)
        self.owner, self.store, self.game = owner, owner.store, game
        self.session = self.store.session(game)
        self.session.tab = 'gallery'
        self.session.history.clear()
        self.setWindowTitle(game.title)
        self.setModal(True)
        self.setObjectName("CoverWorkspace")
        self.resize(max(760,owner.width()-24),max(560,owner.height()-24))
        self.cache = {}
        self.gallery_origin=None
        self.search_request=0
        self._closed=False
        self.finished.connect(self.invalidate_requests)
        root = QVBoxLayout(self)
        root.setContentsMargins(0,0,0,0)
        root.setSpacing(0)
        top, header = box(False,margins=8,name="Top")
        self.back_button = Button("back",self.back,text=tr("collection"),compact=True)
        header.addWidget(self.back_button)
        heading, layout = box(spacing=2)
        self.title_label = label(game.title,heading=True)
        self.context_label = label("",muted=True)
        layout.addWidget(self.title_label)
        layout.addWidget(self.context_label)
        header.addWidget(heading,1)
        header.addWidget(Button("close",self.reject,icon_only=True,compact=True))
        root.addWidget(top)
        self.stack = QStackedWidget()
        self.gallery = Gallery(self)
        self.stack.addWidget(self.gallery)
        root.addWidget(self.stack,1)
        self.feedback = label(tr("readonly_hint" if self.store.readonly else "gallery_hint"),muted=True)
        self.feedback.setObjectName("Feedback")
        self.feedback.setMinimumHeight(26)
        root.addWidget(self.feedback)
        footer, row = box(False,margins=6,name="Footer")
        self.pending_label = label("",muted=True)
        row.addWidget(self.pending_label,1)
        self.save = Button("save",lambda:self.owner.show_save(self),compact=True)
        row.addWidget(self.save)
        root.addWidget(footer)
        self.refresh()
        QTimer.singleShot(0,self.gallery.query.setFocus)
        if inspect and game.cover:
            self.inspect(game.cover)

    def pixmap(self, key):
        if not key:
            return QPixmap()
        if key not in self.cache:
            item = self.store.images[key]
            path = Path(item['local_path']) if item.get('local_path') else catalog.REFERENCE/item['file']
            pm = QPixmap(str(path))
            if pm.isNull():
                item['failed'] = True
            self.cache[key] = pm
        return self.cache[key]

    def refresh(self):
        self.title_label.setText(self.game.title)
        self.context_label.setText(tr("game_context",slot=f"{self.game.slot:03}" if self.game.slot else tr('pending'),region=self.game.region or tr('unidentified'),tab=tr({'gallery':'gallery','inspect':'inspection','compare':'comparison'}[self.session.tab])))
        self.pending_label.setText(tr('chosen_pending' if self.game.choice else 'renamed_pending' if self.game.title!=self.game.original else 'no_pending_choice'))
        self.save.setEnabled(self.store.writable and bool(self.store.plan()))
        self.back_button.setText(catalog.action_label('back') if self.session.history else tr('collection'))
        self.gallery.refresh()
        self.owner.refresh_collection()

    def message(self, text):
        self.feedback.setText(text)

    def search(self):
        raise NotImplementedError('A production search adapter is required')

    def invalidate_requests(self,*args):
        self._closed=True
        self.search_request+=1

    def rename(self):
        if self.store.rename(self.game,self.session.query):
            self.message(tr('name_adopted'))
            self.refresh()

    def choose(self, key):
        self.pixmap(key)
        result = self.store.choose(self.game,key)
        if result=='confirm_low':
            self.owner.confirm(tr('low_title'),tr('confirm_low'),lambda:self.confirm_choice(key),self)
            return
        self.message(tr('image_error' if result=='decode_error' else result))
        self.refresh()

    def confirm_choice(self,key):
        self.message(tr(self.store.choose(self.game,key,True)))
        self.refresh()

    def retry_image(self,key):
        viewer=self.stack.currentWidget()
        state=viewer.snapshot() if isinstance(viewer,Viewer) else None
        self.cache.pop(key,None)
        self.store.images[key].pop('failed',None)
        self.pixmap(key)
        self.show_viewer(self.session.tab=='compare',state)
        self.refresh()
        self.message(tr('image_error' if self.store.images[key].get('failed') else 'gallery_hint'))

    def discard(self):
        self.store.discard(self.game)
        self.refresh()
        self.message(tr('discarded'))

    def inspect(self,key):
        if self.session.tab=='gallery':self.gallery_origin=self.gallery.focus_target()
        self.session.navigate('inspect',key)
        self.show_viewer(False)
        self.refresh()

    def compare(self,key):
        if self.session.tab=='gallery':self.gallery_origin=self.gallery.focus_target()
        if self.store.mark_pair(self.game,key):
            self.show_viewer(True)
            self.message(tr('compare_hint'))
        else:
            self.results()
            self.message(tr('first_finalist'))
        self.refresh()

    def show_viewer(self,comparison,state=None):
        if self.stack.count()>1:
            old=self.stack.widget(1)
            self.stack.removeWidget(old)
            old.deleteLater()
        viewer=Viewer(self,comparison)
        self.stack.addWidget(viewer)
        self.stack.setCurrentWidget(viewer)
        QTimer.singleShot(0,viewer.views[0].setFocus)
        if state:QTimer.singleShot(0,lambda:viewer.restore(state))

    def results(self):
        self.session.tab='gallery'
        self.session.history.clear()
        self.stack.setCurrentWidget(self.gallery)
        self.refresh()
        if self.gallery_origin:self.gallery.restore_focus(self.gallery_origin)
        else:self.gallery.query.setFocus()

    def back(self):
        if not self.session.back():
            self.reject()
        elif self.session.tab=='gallery':
            self.stack.setCurrentWidget(self.gallery)
            if self.gallery_origin:self.gallery.restore_focus(self.gallery_origin)
            else:self.gallery.query.setFocus()
        else:
            self.show_viewer(self.session.tab=='compare')
        self.refresh()

    def keyPressEvent(self,event):
        if event.key()==Qt.Key.Key_Escape:
            self.back()
            event.accept()
        else:super().keyPressEvent(event)

    def web_menu(self):
        menu=QMenu(self)
        query=self.session.query+' Dreamcast cover art'
        options=[('Google Images','https://www.google.com/search?'+urlencode({'tbm':'isch','q':query})),('DuckDuckGo Images','https://duckduckgo.com/?'+urlencode({'q':query,'iax':'images','ia':'images'})),('Bing Images','https://www.bing.com/images/search?'+urlencode({'q':query})),('The Cover Project','https://www.google.com/search?'+urlencode({'q':'site:thecoverproject.net '+query}))]
        if self.game.product and not self.game.product.startswith('SLOT'):
            options.append((self.game.product,'https://www.google.com/search?'+urlencode({'tbm':'isch','q':self.game.product+' Dreamcast cover'})))
        for title,url in options:
            menu.addAction(title,lambda u=url:QDesktopServices.openUrl(QUrl(u)))
        menu.popup(self.gallery.web.mapToGlobal(self.gallery.web.rect().bottomLeft()))
        self.web_popup=menu

    def import_local(self):
        from PySide6.QtWidgets import QFileDialog
        paths,_=QFileDialog.getOpenFileNames(self,tr('local_source'),'',tr('images_filter'))
        self.import_paths(paths)

    def import_paths(self, paths):
        added,failed,available=0,0,0
        for raw in paths:
            path=Path(raw)
            try:
                if path.stat().st_size > 32*1024*1024:
                    raise ValueError('oversize')
                pm=QPixmap(str(path))
                if pm.isNull():
                    raise ValueError('decode')
                content='sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
                existing=next((k for k,i in self.store.images.items() if i.get('contentId')==content),None)
                if existing:
                    if existing not in self.store.candidates(self.game):
                        self.session.local.append(existing)
                        added+=1
                    else:available+=1
                    sources=self.store.images[existing].setdefault('duplicate_sources',[])
                    if path.name not in sources:sources.append(path.name)
                    continue
                key='local-'+content[7:]
                self.store.images[key]={'key':key,'local_path':str(path),'title':path.stem,'variant_index':len(self.session.local)+1,'region':'','group':'','width':pm.width(),'height':pm.height(),'contentId':content,'sourceFile':path.name}
                self.session.local.append(key)
                self.cache[key]=pm
                added+=1
            except (OSError,ValueError):
                failed+=1
        self.session.page=max(1,ceil(len(self.store.candidates(self.game))/6))
        self.results()
        self.message(tr('local_import',added=added,failed=failed)+(' '+tr('already_available',count=available) if available else ''))
