import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from cdi_fixtures import classic_cdi
from openmenu_gdemu_manager.services.agent_queries import validate_image, diagnose_destination


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}


def run_cli(tmp_path, *arguments):
    env = dict(os.environ)
    env['OPENMENU_GDEMU_MANAGER_HOME'] = str(tmp_path/'runtime')
    env['OPENMENU_GDEMU_MANAGER_DOCUMENTS'] = str(tmp_path/'documents')
    return subprocess.run([sys.executable, '-m', 'openmenu_gdemu_manager.cli', *map(str, arguments)],
                          env=env, capture_output=True, text=True, encoding="utf-8", timeout=15)


def test_readonly_queries_preserve_destinations_and_report_cdi_bounds(tmp_path):
    source = tmp_path/'source'; source.mkdir(); image = classic_cdi(source/'disc.cdi')
    before = snapshot(tmp_path)
    result = validate_image(image)
    assert result['status'] == 'checked' and result['schema_version'] == 1
    assert result['read_only'] and not result['hardware_verified']
    assert result['cdi']['tracks'][0]['byte_length'] == 6144
    destination = diagnose_destination(source)
    assert not destination['diagnostic']['write_allowed']
    assert destination['read_only'] and snapshot(tmp_path) == before


@pytest.mark.parametrize('case,status,exit_code', [('valid', 'checked', 0), ('truncated', 'invalid', 2), ('unknown', 'unsupported', 3), ('missing', 'unreadable', 4)])
def test_actual_cli_json_exit_codes_and_no_runtime_migration(tmp_path, case, status, exit_code):
    image = tmp_path/'disc.cdi'
    if case != 'missing':
        classic_cdi(image, payload_cut=2048 if case == 'truncated' else 0)
        if case == 'unknown':
            data = bytearray(image.read_bytes()); data[-8:-4] = b'\x09\x00\x00\x80'; image.write_bytes(data)
    before = snapshot(tmp_path)
    process = run_cli(tmp_path, '--language', 'es', 'validate-image', image)
    assert process.returncode == exit_code, process.stderr
    result = json.loads(process.stdout)
    assert result['status'] == status and result['schema_version'] == 1
    assert result['read_only'] and not result['hardware_verified']
    if case == 'unknown':
        assert 'requiere revisión' in result['issues'][0]['message']
        assert result['issues'][0]['code'] == 'version'
    assert snapshot(tmp_path) == before
    assert not (tmp_path/'runtime').exists() and not (tmp_path/'documents').exists()


def test_cli_diagnosis_is_json_and_not_write_authorization(tmp_path):
    destination = tmp_path/'empty'; destination.mkdir()
    before = snapshot(tmp_path)
    process = run_cli(tmp_path, 'diagnose-storage', destination)
    assert process.returncode == 0 and json.loads(process.stdout)['read_only']
    assert snapshot(tmp_path) == before


def test_headless_entry_does_not_import_desktop_toolkit(tmp_path):
    image = classic_cdi(tmp_path/'disc.cdi')
    code = """import sys, importlib.abc
class NoQt(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith('PySide6'): raise AssertionError('GUI imported by agent query')
sys.meta_path.insert(0, NoQt())
from openmenu_gdemu_manager.cli import main
raise SystemExit(main(['validate-image', sys.argv[1]]))
"""
    env = dict(os.environ, OPENMENU_GDEMU_MANAGER_HOME=str(tmp_path/'runtime'))
    process = subprocess.run([sys.executable, '-c', code, str(image)], env=env, capture_output=True, text=True, encoding="utf-8", timeout=15)
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout)['status'] == 'checked'


@pytest.mark.parametrize('language,phrase', [('en', 'Read-only OpenMenu'), ('es', 'Diagnóstico de OpenMenu')])
def test_cli_help_is_localized(tmp_path, language, phrase):
    process = run_cli(tmp_path, '--language', language, '--help')
    assert process.returncode == 0 and phrase in process.stdout


def test_cli_requires_explicit_operation_and_path(tmp_path):
    process = run_cli(tmp_path)
    assert process.returncode == 2 and not process.stdout


@pytest.mark.parametrize('language,phrase', [('en', 'destination is empty'), ('es', 'destino está vacío')])
def test_destination_messages_use_requested_language(tmp_path, language, phrase):
    destination = tmp_path/'empty'; destination.mkdir()
    result = json.loads(run_cli(tmp_path, '--language', language, 'diagnose-storage', destination).stdout)
    diagnostic = result['diagnostic']
    assert diagnostic['reason_code'] == 'empty' and phrase in diagnostic['message']
    assert 'reason' not in diagnostic and 'menu' not in diagnostic


def test_gdi_access_failure_is_not_reported_as_corruption(tmp_path, monkeypatch):
    from openmenu_gdemu_manager.dreamcast.image_errors import ImageIntegrityError
    from openmenu_gdemu_manager.services import agent_queries
    path = tmp_path/'disc.gdi'; path.write_text('1\n1 0 4 2048 track.iso 0')
    def denied(*args):
        try: raise PermissionError('denied')
        except OSError as cause: raise ImageIntegrityError('read failed') from cause
    monkeypatch.setattr(agent_queries, 'validate_source', denied)
    result = agent_queries.validate_image(path)
    assert result['status'] == 'unreadable' and result['issues'][0]['code'] == 'source_unreadable'


def test_cli_exception_envelope_preserves_common_fields(tmp_path, monkeypatch, capsys):
    from openmenu_gdemu_manager import cli
    def failed(*args): raise OSError('injected read failure')
    monkeypatch.setattr(cli, 'diagnose_destination', failed)
    assert cli.main(['diagnose-storage', str(tmp_path)]) == 4
    result = json.loads(capsys.readouterr().out)
    assert result['read_only'] and not result['hardware_verified']
    assert result['path'] == str(tmp_path) and result['operation'] == 'diagnose_destination'
    assert result['issues'][0]['category'] == 'unreadable'
