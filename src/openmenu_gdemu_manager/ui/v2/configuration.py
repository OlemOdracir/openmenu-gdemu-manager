"""Localized presentation of configuration findings; never a storage gate."""
from html import escape
from ...i18n import tr
from ...dreamcast.gdemu_config import RANGES

PREFIX = "v2.gdemu_config."
MAX_DISPLAY_ITEMS = 20


def expected_value(option):
    low, high = RANGES[option]
    if option in ('image_tests', 'high_speed'):
        return tr(PREFIX + 'boolean')
    if option == 'read_limit':
        return tr(PREFIX + 'read_limit_range', low=low, high=high)
    text = tr(PREFIX + 'range', low=low, high=high)
    return tr(PREFIX + 'milliseconds', bounds=text) if option in ('open_time', 'detect_time') else text


def summary(configuration):
    return tr(PREFIX + configuration.status) if configuration else ""


def details(configuration):
    if configuration is None:
        return ""
    rows = [f"<b>GDEMU.ini:</b> {escape(summary(configuration))}", escape(tr(PREFIX + "preserved"))]
    for setting in configuration.settings[:MAX_DISPLAY_ITEMS]:
        value = setting.value
        # The file is bounded, but long malformed values must not dominate UI.
        if len(value) > 80:
            value = value[:80] + "…"
        rows.append(escape(tr(PREFIX + "setting", line=setting.line, option=setting.key, value=value)))
    if len(configuration.settings) > MAX_DISPLAY_ITEMS:
        rows.append(escape(tr(PREFIX + 'more_settings', count=len(configuration.settings) - MAX_DISPLAY_ITEMS)))
    for finding in configuration.findings[:MAX_DISPLAY_ITEMS]:
        key = finding.key[:80]
        rows.append(escape(tr(PREFIX + "finding." + finding.code, line=finding.line, option=key, expected=expected_value(finding.key) if finding.code == "value" else "")))
    if len(configuration.findings) > MAX_DISPLAY_ITEMS:
        rows.append(escape(tr(PREFIX + 'more_findings', count=len(configuration.findings) - MAX_DISPLAY_ITEMS)))
    return "<br>".join(rows)



def show_dialog(parent, configuration):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QScrollArea
    from .design import label, Button
    dialog = QDialog(parent)
    dialog.setWindowTitle(tr(PREFIX + 'title'))
    dialog.resize(660, 420)
    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(20, 16, 20, 16)
    layout.setSpacing(12)
    layout.addWidget(label(tr(PREFIX + 'title'), heading=True))
    layout.addWidget(label(str(configuration.path), muted=True, wrap=True))
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    content = label('', wrap=True)
    content.setTextFormat(Qt.TextFormat.RichText)
    content.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
    content.setText(details(configuration))
    scroll.setWidget(content)
    layout.addWidget(scroll, 1)
    footer = QHBoxLayout()
    footer.addStretch(1)
    close = Button('cancel', dialog.reject, text=tr('action.close'))
    close.setDefault(True)
    footer.addWidget(close)
    layout.addLayout(footer)
    dialog.exec()
    dialog.deleteLater()
