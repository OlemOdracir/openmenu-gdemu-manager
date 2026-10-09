"""Compact collection over the original model; no storage behavior lives here."""
from PySide6.QtCore import Qt,QRectF,QEvent,QPointF
from PySide6.QtGui import QColor,QPainter,QPen,QFont
from PySide6.QtWidgets import QStyledItemDelegate,QHeaderView
from ..widgets import GamesTableModel
from .catalog import tr
from .design import colors,icon


def paint_check(painter,rect,checked,partial=False):
    c=colors()
    rect=QRectF(rect.center().x()-9,rect.center().y()-9,18,18)
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor(c['accent'] if checked or partial else c['muted']),1.5))
    painter.setBrush(QColor(c['accent'] if checked or partial else c['paper']))
    painter.drawRoundedRect(rect,3,3)
    painter.setPen(QPen(QColor(c['paper']),2,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap))
    if partial:painter.drawLine(rect.topLeft()+QPointF(4,9),rect.topLeft()+QPointF(14,9))
    elif checked:
        painter.drawLine(int(rect.x()+4),int(rect.y()+9),int(rect.x()+8),int(rect.y()+13))
        painter.drawLine(int(rect.x()+8),int(rect.y()+13),int(rect.x()+14),int(rect.y()+5))
    painter.restore()


class CollectionModel(GamesTableModel):
    def __init__(self,window):super().__init__(window);self.window=window

    def data(self,index,role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():return None
        game=self._games[index.row()]
        if role==Qt.ItemDataRole.BackgroundRole:
            c=colors()
            return QColor(c['danger_soft'] if game.pending_delete else c['accent_soft'] if self._bulk_mode and self._bulk_checked.get(game.slot) else c['surface'])
        if role==Qt.ItemDataRole.DisplayRole:
            col=index.column()
            if col==self.C_SLOT:return '+' if game.pending_add else f'{game.slot:03d}'
            if col==self.C_REGION:return game.region or tr('unidentified')
            if col==self.C_STATUS:
                draft=self.window.cover_host.store.view(game).choice if self.window.cover_host else None
                parts=[tr('no_cover' if game.has_placeholder_cover or not game.current_cover else 'with_cover')]
                if game.pending_delete:parts.append(tr('remove_pending'))
                elif game.pending_add:parts.append(tr('new_pending'))
                elif draft or game.save_status=='pendiente_guardar':parts.append(tr('pending'))
                elif game.slot in self._proposals:parts.append(tr('proposal'))
                return '\n'.join(parts)
        return super().data(index,role)


class CollectionDelegate(QStyledItemDelegate):
    def editorEvent(self,event,model,option,index):
        if index.column()==model.C_CHECK and model._bulk_mode:
            if event.type()==QEvent.Type.MouseButtonRelease and event.button()==Qt.MouseButton.LeftButton or event.type()==QEvent.Type.KeyPress and event.key()==Qt.Key.Key_Space:
                game=model._games[index.row()]
                if game.pending_delete:return False
                value=Qt.CheckState.Unchecked.value if model._bulk_checked.get(game.slot,False) else Qt.CheckState.Checked.value
                return model.setData(index,value,Qt.ItemDataRole.CheckStateRole)
            return False
        return super().editorEvent(event,model,option,index)

    def paint(self,painter,option,index):
        model=index.model();game=model._games[index.row()];c=colors()
        painter.save()
        bg=model.data(index,Qt.ItemDataRole.BackgroundRole)
        painter.fillRect(option.rect,bg or QColor(c['surface']))
        rect=option.rect.adjusted(8,4,-8,-4)
        col=index.column()
        if col==model.C_CHECK:paint_check(painter,rect,model._bulk_checked.get(game.slot,False))
        elif col==model.C_COVER:
            # Pending proposals never impersonate a cover already saved on SD.
            pm=model._cover_pixmap(game,None)
            if game.has_placeholder_cover or not game.current_cover:icon('photo').paint(painter,rect.center().x()-12,rect.center().y()-12,24,24)
            elif pm and not pm.isNull():
                scaled=pm.scaled(rect.size(),Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)
                painter.drawPixmap(rect.center().x()-scaled.width()//2,rect.center().y()-scaled.height()//2,scaled)
        elif col==model.C_NAME:
            font=QFont(option.font);font.setWeight(QFont.Weight.DemiBold)
            painter.setFont(font);painter.setPen(QColor(c['ink']))
            text=option.fontMetrics.elidedText(game.name,Qt.TextElideMode.ElideRight,rect.width())
            painter.drawText(rect.adjusted(0,0,0,-rect.height()//2),Qt.AlignmentFlag.AlignVCenter,text)
            font.setWeight(QFont.Weight.Normal);font.setPixelSize(11);painter.setFont(font);painter.setPen(QColor(c['muted']))
            painter.drawText(rect.adjusted(0,rect.height()//2,0,0),Qt.AlignmentFlag.AlignVCenter,game.product_id or tr('identification_pending'))
        else:
            tone=c['focus'] if col==model.C_REGION else c['danger'] if game.pending_delete else c['warning'] if col==model.C_STATUS and (game.has_placeholder_cover or not game.current_cover) else c['ink']
            painter.setPen(QColor(tone));painter.drawText(rect,Qt.AlignmentFlag.AlignVCenter|Qt.TextFlag.TextWordWrap,str(model.data(index) or ''))
        painter.setPen(QColor(c['line']));painter.drawLine(option.rect.bottomLeft(),option.rect.bottomRight())
        painter.restore()


class CollectionHeader(QHeaderView):
    def __init__(self,window):super().__init__(Qt.Orientation.Horizontal,window.table);self.window=window
    def paintSection(self,painter,rect,index):
        if index!=GamesTableModel.C_CHECK or not self.window.bulk_mode:
            return super().paintSection(painter,rect,index)
        painter.save();painter.fillRect(rect,QColor(colors()['surface']))
        targets=[g for g in self.window.games if not g.pending_delete]
        count=sum(bool(self.window.bulk_checked.get(g.slot)) for g in targets)
        check=rect.adjusted(0,0,-max(0,rect.width()-32),0)
        paint_check(painter,check,bool(targets) and count==len(targets),0<count<len(targets))
        painter.setPen(QColor(colors()['muted']))
        painter.drawText(rect.adjusted(33,0,0,0),Qt.AlignmentFlag.AlignVCenter,tr('all'))
        painter.restore()
