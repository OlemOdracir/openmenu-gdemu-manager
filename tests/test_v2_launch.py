"""Exercise the repository-root entry points in a fresh interpreter."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tomllib

ROOT=Path(__file__).resolve().parents[1]


def project_version():
    return tomllib.loads((ROOT/'pyproject.toml').read_text(encoding='utf-8'))['project']['version']


def test_root_import_and_about_use_shared_current_metadata():
    script="import json; import openmenu_gdemu_manager as p; from openmenu_gdemu_manager.ui.dialogs.about import app_version; print(json.dumps({'version':p.__version__,'about':app_version(),'file':p.__file__}))"
    result=subprocess.run([sys.executable,'-c',script],cwd=ROOT,capture_output=True,text=True,timeout=25,check=True)
    payload=json.loads(result.stdout)
    assert Path(payload['file']).resolve()==ROOT/'openmenu_gdemu_manager/__init__.py'
    assert payload['version']==payload['about']==project_version()


def test_root_module_launch_self_test_reports_current_version(tmp_path):
    report=tmp_path/'report.json'
    environment=dict(os.environ,QT_QPA_PLATFORM='offscreen',LOCALAPPDATA=str(tmp_path/'runtime'),USERPROFILE=str(tmp_path/'profile'))
    for key in ('OPENMENU_GDEMU_MANAGER_HOME','OPENMENU_GDEMU_MANAGER_DOCUMENTS'):environment.pop(key,None)
    subprocess.run([sys.executable,'-m','openmenu_gdemu_manager','--self-test',str(report)],cwd=ROOT,env=environment,capture_output=True,text=True,timeout=25,check=True)
    payload=json.loads(report.read_text(encoding='utf-8'))
    assert payload=={'version':project_version(),'startup':True,'icons':True,'errors':[],'sd_scanned':False,'network_requested':False}
