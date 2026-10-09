import sys
from ..ui.main_window import run as run_original, MainWindow
from ..ui.v2.main_window import MainWindowV2


def run():
    if '--self-test' in sys.argv:
        from .self_test import run as self_test
        index=sys.argv.index('--self-test')
        if index+1>=len(sys.argv):raise ValueError('--self-test requires a report path')
        raise SystemExit(self_test(sys.argv[index+1]))
    return run_original(window_class=MainWindow if '--legacy-ui' in sys.argv else MainWindowV2)


__all__ = ['run']
