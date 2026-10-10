"""Portable startup smoke check, without SD scanning, network or game fixtures."""
import json
from pathlib import Path
from PySide6.QtWidgets import QApplication,QMessageBox
from .. import __version__
from ..ui.v2.main_window import MainWindowV2
from ..ui.v2.design import icon
from ..ui.v2.catalog import ACTIONS


def run(report_path):
    app=QApplication.instance() or QApplication([])
    failures=[]
    def failed(*args):failures.append(str(args[-1]))
    QMessageBox.critical=failed
    window=MainWindowV2(initial_root=Path(report_path).resolve().parent)
    window.show();app.processEvents()
    assets=all(not icon(spec['icon']).isNull() for spec in ACTIONS.values())
    report={'version':__version__,'startup':window._v2_ready,'icons':assets,'errors':failures,'sd_scanned':False,'network_requested':False}
    Path(report_path).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    window.close();app.processEvents()
    return 0 if window._v2_ready and assets and not failures else 1
