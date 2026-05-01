"""Run the src-layout package when invoked as `py -m openmenu_gdemu_manager`."""

from pathlib import Path
import runpy
import sys


root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "src"))
sys.modules.pop("openmenu_gdemu_manager", None)
runpy.run_module("openmenu_gdemu_manager", run_name="__main__", alter_sys=True)
