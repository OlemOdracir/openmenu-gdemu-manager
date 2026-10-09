from __future__ import annotations

from PySide6.QtCore import QByteArray, QSize, Qt, Signal, QRectF
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPen, QPixmap, QFont, QFontDatabase
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QAbstractButton, QCheckBox, QFrame, QLabel, QPushButton, QSizePolicy, QHBoxLayout, QVBoxLayout, QStyleOptionButton, QStyle, QLineEdit

from . import catalog

theme = "light"

# Pixel-valued V5 tokens are shared with Qt. Metadata and compact icons have
# explicit V5 CSS overrides (candidate-caption/table-head and candidate-actions);
# they are named here rather than confused with small text or regular icons.
METRICS = {
    key: int(value[:-2])
    for key, value in catalog.TOKENS["metrics"].items()
    if isinstance(value, str) and value.endswith("px")
}
METRICS.update({"font-metadata": 11, "icon-compact": 17, "font-collection-heading": 24})


def colors():
    return catalog.TOKENS[theme]


def icon(name, color=None, size=METRICS["icon"]):
    color = color or colors()["ink"]
    raw = (catalog.REFERENCE / "icons" / f"{name}.svg").read_bytes().replace(b"currentColor", color.encode())
    svg = QSvgRenderer(QByteArray(raw))
    # Render at 2x for high-DPI edges. QIcon retains the logical 20px size.
    pm = QPixmap(size * 2, size * 2)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    svg.render(painter)
    painter.end()
    pm.setDevicePixelRatio(2)
    return QIcon(pm)


def apply_theme(app, value="light"):
    global theme
    theme = value
    c = colors()
    # Windows' offscreen QPA does not enumerate system fonts. Load installed
    # fonts for native render tests; no font file is copied into the project.
    if not QFontDatabase.families():
        from pathlib import Path
        for name in ('segoeui.ttf','segoeuib.ttf','seguisb.ttf'):
            path = Path('C:/Windows/Fonts') / name
            if path.is_file():
                QFontDatabase.addApplicationFont(str(path))
    font = QFont("Segoe UI")
    font.setPixelSize(METRICS["font-body"])
    app.setFont(font)
    app.setStyle("Fusion")
    app.setStyleSheet(f"""
    QWidget {{ color: {c['ink']}; font-family: 'Segoe UI'; font-size: {METRICS['font-body']}px; }}
    QMainWindow, QDialog, QWidget#Surface {{ background: {c['surface']}; }}
    QDialog {{ border-top: 3px solid {c['accent']}; }}
    QWidget#Chrome {{ background: {c['chrome']}; }}
    QWidget#Chrome QLabel {{ color: {c['chrome_ink']}; font-size: 12px; }}
    QLabel {{ background: transparent; }}
    QLabel[muted=true] {{ color: {c['muted']}; font-size: {METRICS['font-metadata']}px; }}
    QLabel[heading=true] {{ font-size: {METRICS['font-title']}px; font-weight: 600; }}
    QLabel[collectionHeading=true] {{ font-size: {METRICS['font-collection-heading']}px; border-left: 3px solid {c['accent']}; padding-left: {METRICS['space-2']}px; }}
    QLabel[title=true] {{ font-size: {METRICS['font-body']}px; font-weight: 600; }}
    QLabel[tone=success] {{ color: {c['success']}; }}
    QLabel[tone=warning] {{ color: {c['warning']}; }}
    QLabel[tone=danger] {{ color: {c['danger']}; }}
    QLabel[tone=pending] {{ color: {c['success']}; font-weight: 600; }}
    QLabel[tone=region] {{ color: {c['focus']}; font-size: {METRICS['font-small']}px; }}
    QFrame#Card, QFrame#Reference {{ border: 1px solid {c['line']}; border-radius: {METRICS['radius']}px; background: {c['paper']}; }}
    QFrame#Card[chosen=true] {{ border-color: {c['success']}; }}
    QFrame#Row {{ border-bottom: 1px solid {c['line']}; background: {c['surface']}; }}
    QFrame#Row[selected=true] {{ background: {c['accent_soft']}; }}
    QFrame#Row[removed=true] {{ background: {c['soft']}; }}
    QFrame#Top {{ border-bottom: 1px solid {c['line']}; }}
    QFrame#Footer {{ border-top: 1px solid {c['line']}; }}
    QWidget#WizardHero, QWidget#SecurityCard, QWidget#DiagnosticTile {{ background: {c['paper']}; border: 1px solid {c['line']}; border-radius: {METRICS['radius']}px; }}
    QLabel#ChipWarning {{ background: {c['warning_soft']}; color: {c['warning']}; padding: 8px; border-radius: {METRICS['radius']}px; }}
    QLabel#ChipInfo {{ background: {c['soft']}; color: {c['ink']}; padding: 8px; border-radius: {METRICS['radius']}px; }}
    QLabel#TileTitle {{ color: {c['muted']}; font-size: {METRICS['font-small']}px; }}
    QLabel#BusyTitle {{ font-weight: 600; }}
    QLabel#BusyDetail {{ color: {c['muted']}; }}
    QWidget#BusyOverlay {{ background: rgba(8, 15, 20, 0.55); }}
    QWidget#BusyPanel {{ background: {c['paper']}; border: 1px solid {c['line']}; border-radius: {METRICS['radius']}px; }}
    QLabel#Guidance {{ background: {c['success_soft']}; color: {c['success']}; border-left: 3px solid {c['success']}; padding: 8px 12px; font-size: 12px; }}
    QLabel#Feedback {{ background: {c['soft']}; color: {c['muted']}; padding: 5px 12px; font-size: {METRICS['font-metadata']}px; }}
    QPushButton {{ min-height: 30px; border: 1px solid {c['line']}; border-radius: {METRICS['radius']}px; padding: 4px 8px; background: {c['paper']}; font-size: {METRICS['font-small']}px; }}
    QPushButton[compact=true] {{ min-height: 22px; }}
    QPushButton[destination=true] {{ min-height: 48px; }}
    QPushButton:hover {{ border-color: {c['accent']}; }}
    QPushButton:focus, QLineEdit:focus, QComboBox:focus {{ border: 2px solid {c['focus']}; }}
    QPushButton[role=primary] {{ color: {c['paper']}; background: {c['accent']}; border-color: {c['accent']}; font-weight: 600; }}
    QPushButton[role=danger] {{ color: {c['danger']}; background: {c['danger_soft']}; border-color: {c['danger']}; }}
    QPushButton:checked {{ background: {c['accent_soft']}; border-color: {c['accent']}; color: {c['accent']}; }}
    QPushButton[attention=true] {{ border: 2px solid {c['success']}; background: {c['success_soft']}; }}
    QPushButton:disabled {{ background: {c['soft']}; color: {c['muted']}; border-color: {c['line']}; font-weight: 400; }}
    QLineEdit, QComboBox {{ background: {c['paper']}; border: 1px solid {c['line']}; border-radius: 5px; padding: 6px 8px; min-height: 26px; font-size: 12px; }}
    QSpinBox {{ background: {c['paper']}; border: 1px solid {c['line']}; border-radius: 5px; padding: 4px 8px; min-height: 26px; }}
    QGroupBox {{ border: 1px solid {c['line']}; border-radius: 5px; margin-top: 12px; padding-top: 8px; }}
    QProgressBar {{ border: 1px solid {c['line']}; border-radius: 5px; background: {c['soft']}; color: {c['ink']}; min-height: 16px; text-align: center; }}
    QProgressBar::chunk {{ background: {c['accent']}; border-radius: 4px; }}
    QTableWidget {{ background: {c['paper']}; gridline-color: {c['line']}; selection-background-color: {c['accent_soft']}; selection-color: {c['ink']}; border: 1px solid {c['line']}; }}
    QHeaderView::section {{ background: {c['surface']}; color: {c['muted']}; border: 0; border-bottom: 1px solid {c['line']}; padding: 6px; }}
    QScrollArea {{ border: none; background: {c['surface']}; }}
    QScrollBar:vertical {{ width: 12px; background: {c['soft']}; margin: 0; }}
    QScrollBar::handle:vertical {{ background: {c['muted']}; border-radius: 5px; min-height: 28px; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar:horizontal {{ height: 12px; background: {c['soft']}; }}
    QScrollBar::handle:horizontal {{ background: {c['muted']}; min-width: 28px; border-radius: 5px; }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
    QMenu {{ background: {c['paper']}; border: 1px solid {c['line']}; }}
    QMenu::item:selected {{ background: {c['accent_soft']}; }}
    QToolTip {{ background: {c['paper']}; color: {c['ink']}; border: 1px solid {c['line']}; }}
    """)
    for widget in app.allWidgets():
        if isinstance(widget, Button):
            widget.refresh_icon()
        if isinstance(widget,QLineEdit):
            for action in widget.actions():
                if action.objectName()=='query_clear':action.setIcon(icon('x'))
        widget.update()
    from .retained_dialogs import install, refresh_all
    install(app)
    refresh_all(app)


def repolish(widget):
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def clearable_edit(text,name):
    edit=QLineEdit(text)
    edit.setAccessibleName(name)
    action=QAction(icon('x'),catalog.action_label('query_clear'),edit)
    action.setObjectName('query_clear')
    action.setToolTip(catalog.action_label('query_clear'))
    action.triggered.connect(lambda: (edit.clear(),edit.setFocus()))
    edit.addAction(action,QLineEdit.ActionPosition.TrailingPosition)
    edit.textChanged.connect(lambda text:action.setEnabled(bool(text)))
    action.setEnabled(bool(text))
    return edit


class Button(QPushButton):
    def __init__(self, action, callback=None, text=None, *, icon_only=False, compact=False, role=None, parent=None):
        spec = catalog.ACTIONS[action]
        super().__init__(catalog.action_label(action) if text is None else text, parent)
        self.action = action
        self.setObjectName(action)
        self.setProperty("role", role or spec["role"])
        self.setProperty("compact", compact)
        self.setToolTip(text or catalog.action_label(action))
        self.setAccessibleName(text or catalog.action_label(action))
        icon_size = METRICS["icon-compact" if compact else "icon"]
        control_size = METRICS["control-compact" if compact else "control"]
        self.setIconSize(QSize(icon_size, icon_size))
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(control_size)
        if icon_only:
            self.setText("")
            self.setFixedSize(control_size, control_size)
        if callback:
            self.clicked.connect(callback)
        self.refresh_icon()

    def refresh_icon(self):
        c = colors()
        role = self.property("role")
        color = c["muted"] if not self.isEnabled() else c["paper"] if role == "primary" else c["danger"] if role == "danger" else c["ink"]
        self.setIcon(icon(catalog.ACTIONS[self.action]["icon"], color))

    def setEnabled(self, value):
        super().setEnabled(value)
        if hasattr(self, "action"):
            self.refresh_icon()


class SelectionCheck(QCheckBox):
    """Native check state/key handling; shared 18px indicator and 32px target."""

    def __init__(self, caption="", name="", parent=None):
        super().__init__(caption, parent)
        self.setAccessibleName(name or caption)
        self.setMinimumHeight(METRICS["selection-target"])
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def sizeHint(self):
        target = METRICS["selection-target"]
        return QSize(target + (self.fontMetrics().horizontalAdvance(self.text()) + 4 if self.text() else 0), target)

    def hitButton(self, point):
        return self.rect().contains(point)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = colors()
        partial = self.checkState() == Qt.CheckState.PartiallyChecked
        filled = self.isChecked() or partial
        size = METRICS["selection-size"]
        rect = QRectF((METRICS["selection-target"] - size) / 2, (self.height() - size) / 2, size, size)
        p.setOpacity(1 if self.isEnabled() else .5)
        p.setPen(QPen(QColor(c["accent"] if filled else c["muted"]), 1.5))
        p.setBrush(QColor(c["accent"] if filled else c["paper"]))
        p.drawRoundedRect(rect, 3, 3)
        p.setPen(QPen(QColor(c["paper"]), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        if partial:
            p.drawLine(int(rect.x() + 4), int(rect.center().y()), int(rect.right() - 4), int(rect.center().y()))
        elif self.isChecked():
            p.drawLine(int(rect.x()+4), int(rect.y()+9), int(rect.x()+8), int(rect.y()+13))
            p.drawLine(int(rect.x()+8), int(rect.y()+13), int(rect.x()+14), int(rect.y()+5))
        if self.text():
            p.setPen(QColor(c["ink"]))
            p.drawText(self.rect().adjusted(32, 0, 0, 0), Qt.AlignmentFlag.AlignVCenter, self.text())
        if self.hasFocus():
            p.setPen(QPen(QColor(c["focus"]), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(QRectF(3, rect.y()-4, self.width()-6, 26), 5, 5)


class DestinationButton(Button):
    def __init__(self, callback, title, subtitle):
        super().__init__('browse', callback, text='')
        self.destination_title, self.destination_subtitle = title, subtitle
        self.setProperty('destination', True)
        self.setAccessibleName(title+' · '+subtitle)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed)

    def paintEvent(self, event):
        painter=QPainter(self)
        option=QStyleOptionButton()
        self.initStyleOption(option)
        option.icon=QIcon()
        option.text=''
        self.style().drawControl(QStyle.ControlElement.CE_PushButton,option,painter,self)
        icon('device-sd-card',colors()['accent'],30).paint(painter,12,(self.height()-30)//2,30,30)
        font=QFont('Segoe UI')
        font.setPixelSize(16)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.setPen(QColor(colors()['ink']))
        painter.drawText(self.rect().adjusted(54,7,-12,-self.height()+29),Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,self.destination_title)
        font.setPixelSize(12)
        font.setWeight(QFont.Weight.Normal)
        painter.setFont(font)
        painter.setPen(QColor(colors()['muted']))
        text=self.fontMetrics().elidedText(self.destination_subtitle,Qt.TextElideMode.ElideRight,max(1,self.width()-66))
        painter.drawText(self.rect().adjusted(54,29,-12,-5),Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,text)

    def set_destination(self,title,subtitle):
        self.destination_title,self.destination_subtitle=title,subtitle
        self.setAccessibleName(title+' · '+subtitle)
        self.update()


class ImageTile(QAbstractButton):
    def __init__(self, pixmap=None, name="", parent=None):
        super().__init__(parent)
        self.pm = pixmap or QPixmap()
        self.setAccessibleName(name or catalog.tr("no_cover"))
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.setMinimumSize(40, 40)

    def sizeHint(self):
        return QSize(120, 120)

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(colors()["soft"]))
        if not self.pm.isNull():
            target = self.pm.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            rect = QRectF((self.width()-target.width())/2, (self.height()-target.height())/2, target.width(), target.height())
            p.drawPixmap(rect, self.pm, QRectF(self.pm.rect()))
        else:
            icon("photo", colors()["muted"]).paint(p, (self.width()-24)//2, (self.height()-24)//2, 24, 24)
        if self.hasFocus():
            p.setPen(QPen(QColor(colors()["focus"]), 2))
            p.drawRect(self.rect().adjusted(1,1,-2,-2))


class TextLabel(QLabel):
    def minimumSizeHint(self):
        hint=super().minimumSizeHint()
        # Allow horizontal layouts to shrink text without losing fixed-width
        # column allocation (Ignored policy would allocate fixed widgets as 0).
        return QSize(0,hint.height())


def label(text, *, muted=False, title=False, heading=False, wrap=False, tone=None):
    item = TextLabel(text)
    item.setProperty("muted", muted)
    item.setProperty("title", title)
    item.setProperty("heading", heading)
    if tone:
        item.setProperty("tone", tone)
    item.setWordWrap(wrap)
    item.setTextFormat(Qt.TextFormat.PlainText)
    item.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
    return item


def box(vertical=True, margins=0, spacing=8, name=None):
    widget = QFrame()
    if name:
        widget.setObjectName(name)
    layout = QVBoxLayout(widget) if vertical else QHBoxLayout(widget)
    layout.setContentsMargins(margins, margins, margins, margins)
    layout.setSpacing(spacing)
    return widget, layout
