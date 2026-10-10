"""Failure reproduction: trace retention, rotation, startup and agent isolation."""
import json
import logging
import os
from pathlib import Path
import re
import subprocess
import sys
import threading

import pytest

from openmenu_gdemu_manager.app import logger as diagnostics


@pytest.fixture
def log_file(tmp_path, monkeypatch):
    root = logging.getLogger()
    handlers, level = list(root.handlers), root.level
    hooks = sys.excepthook, threading.excepthook
    active = diagnostics.active_log_path()
    path = tmp_path / "runtime" / "app.log"
    monkeypatch.setattr(diagnostics, "LOG_PATH", path)
    path = diagnostics.setup_logging()
    yield path
    for handler in root.handlers:
        if handler not in handlers: handler.close()
    root.handlers = handlers
    root.setLevel(level)
    sys.excepthook, threading.excepthook = hooks
    diagnostics._active_log_path = active


def test_worker_failures_retain_traceback_and_operation_context(log_file, monkeypatch):
    from openmenu_gdemu_manager.ui.v2 import import_games, bridge
    from openmenu_gdemu_manager.core.models import Candidate
    class BrokenPaths:
        def __iter__(self): raise RuntimeError("inspection origin marker")
    inspect = import_games.InspectWorker(BrokenPaths(), {"GDI"})
    errors = []
    inspect.error.connect(errors.append)
    inspect.run()
    def fail(*args): raise RuntimeError("image origin marker")
    monkeypatch.setattr(bridge, "load_candidate_image", fail)
    candidate = Candidate("synthetic-provider", "Sample", 0, url="https://example.test/cover?token=fake-private-token")
    retry = bridge.RetryImageWorker(candidate)
    retry.error.connect(errors.append)
    retry.run()
    search = bridge.CoverSearchWorker(None, "Sample", False)
    results = []
    search.finished.connect(results.append)
    search.prepare({"candidates": [candidate]})
    assert errors == ["inspection origin marker", "image origin marker"]
    assert results[0]["items"][0][2] == "image origin marker"
    text = log_file.read_text(encoding="utf-8")
    assert text.count("Traceback (most recent call last)") == 3
    for operation in ("inspect_games", "retry_cover_image", "prepare_cover_images"):
        assert re.search(r"operation=" + operation + r" operation_id=[a-f0-9]{32}", text)
    assert "synthetic-provider" in text and "query=Sample" in text
    assert "fake-private-token" not in text and "token=[redacted]" in text


def test_local_image_rejection_logs_file_and_cause(log_file, tmp_path):
    from types import SimpleNamespace
    from openmenu_gdemu_manager.ui.v2.covers import CoverWorkspace
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    bad = tmp_path / "bad-image.png"
    bad.write_bytes(b"not an image")
    messages = []
    workspace = SimpleNamespace(store=SimpleNamespace(candidates=lambda game: []),
        game=None, session=SimpleNamespace(page=1), results=lambda: None, message=messages.append)
    CoverWorkspace.import_paths(workspace, [str(bad)])
    text = log_file.read_text(encoding="utf-8")
    assert str(bad) in text and "ValueError: decode" in text
    assert "operation=import_local_covers" in text and messages


def test_save_failure_keeps_id_without_mutating_blocked_destination(log_file, tmp_path):
    from openmenu_gdemu_manager.ui.workers import SaveChangesWorker
    from openmenu_gdemu_manager.services.transaction_log import transactions_path
    destination = tmp_path / "destination"
    destination.mkdir()
    sentinel = destination / "keep.txt"
    sentinel.write_text("preserve", encoding="utf-8")
    worker = SaveChangesWorker(destination, [], {}, write_allowed=False)
    errors = []
    worker.error.connect(errors.append)
    worker.run()
    text = log_file.read_text(encoding="utf-8")
    ids = re.findall(r"operation=save_changes operation_id=([a-f0-9]{32})", text)
    assert len(ids) >= 2 and len(set(ids)) == 1
    assert "PermissionError" in text and errors
    assert sentinel.read_text() == "preserve" and not transactions_path(destination).exists()


def test_log_rotates_and_preserves_session_banner(log_file):
    text = log_file.read_text(encoding="utf-8")
    assert "Session started: app=" in text and "Python=" in text and "platform=" in text
    assert re.search(r"session=[a-f0-9]{32} thread=", text)
    handler = next(h for h in logging.getLogger().handlers if isinstance(h, diagnostics.RotatingFileHandler))
    handler.maxBytes = 512  # trigger the actual production rotation with small fixtures
    for n in range(30): logging.getLogger("synthetic").info("event %s %s", n, "x" * 180)
    files = list(log_file.parent.glob(log_file.name + "*"))
    assert len([p for p in files if not p.name.endswith(".lock")]) == diagnostics.BACKUP_COUNT + 1
    assert "event 29" in log_file.read_text() and "event 0 " not in ''.join(p.read_text() for p in files if not p.name.endswith('.lock'))


def test_thread_and_qt_messages_reach_persistent_log(log_file):
    def fail(): raise RuntimeError("thread origin marker")
    thread = threading.Thread(target=fail, name="diagnostic-thread")
    thread.start()
    thread.join(timeout=5)
    assert not thread.is_alive()
    from PySide6.QtCore import qInstallMessageHandler, qWarning
    previous = diagnostics.install_qt_logging()
    try: qWarning("qt origin marker")
    finally: qInstallMessageHandler(previous)
    text = log_file.read_text(encoding="utf-8")
    assert "RuntimeError: thread origin marker" in text and "thread=diagnostic-thread" in text
    assert "qt origin marker" in text and "Qt initialized: version=" in text


def test_known_credentials_are_masked_in_exception_trace(log_file):
    try:
        raise RuntimeError("https://user:fake-auth@host.test/?devpassword=fake-dev&sspassword=fake-ss&api_key=fake-key Authorization: Bearer fake-bearer")
    except RuntimeError: logging.getLogger("synthetic").exception("Remote failure")
    text = log_file.read_text(encoding="utf-8")
    assert "RuntimeError" in text
    for secret in ("fake-auth", "fake-dev", "fake-ss", "fake-key", "fake-bearer"):
        assert secret not in text
    assert text.count("[redacted]") >= 5


def test_unwritable_runtime_uses_discoverable_temporary_log(log_file, tmp_path, monkeypatch):
    blocked = tmp_path / "blocked"
    blocked.write_text("file, not directory")
    monkeypatch.setattr(diagnostics, "LOG_PATH", blocked / "app.log")
    monkeypatch.setattr(diagnostics.tempfile, "gettempdir", lambda: str(tmp_path / "temporary"))
    actual = diagnostics.setup_logging()
    assert actual == diagnostics.active_log_path()
    assert "using temporary log" in actual.read_text(encoding="utf-8")
    assert blocked.read_text() == "file, not directory"


def test_windowed_process_without_console_still_logs(log_file, monkeypatch):
    monkeypatch.setattr(sys, "stderr", None)
    monkeypatch.setattr(sys, "stdout", None)
    actual = diagnostics.setup_logging()
    logging.getLogger("synthetic").error("windowed marker")
    assert "windowed marker" in actual.read_text(encoding="utf-8")


def test_qt_import_failure_is_captured_before_bootstrap(tmp_path):
    code = """import sys, importlib.abc
class BlockQt(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'PySide6.QtCore': raise ImportError('synthetic QtCore DLL failure')
sys.meta_path.insert(0, BlockQt())
from openmenu_gdemu_manager.__main__ import main
main()
"""
    env = dict(os.environ, OPENMENU_GDEMU_MANAGER_HOME=str(tmp_path / "runtime"),
               OPENMENU_GDEMU_MANAGER_DOCUMENTS=str(tmp_path / "documents"))
    process = subprocess.run([sys.executable, "-c", code], cwd=tmp_path, env=env,
                             capture_output=True, text=True, timeout=20)
    assert process.returncode != 0
    text = next((tmp_path / "runtime").glob("openmenu_gdemu_manager.*.log")).read_text(encoding="utf-8")
    assert "synthetic QtCore DLL failure" in text and "Traceback" in text
    assert "operation=startup" in text


def test_cli_failure_correlates_stderr_with_json_and_restores_host(tmp_path, monkeypatch, capsys):
    from openmenu_gdemu_manager import cli
    def fail(*args): raise RuntimeError("agent origin marker token=fake-agent-secret")
    monkeypatch.setattr(cli, "diagnose_destination", fail)
    parent = logging.getLogger(diagnostics.AGENT_LOGGER)
    before = list(parent.handlers), parent.level, parent.propagate
    files = list(tmp_path.rglob("*"))
    assert cli.main(["diagnose-storage", str(tmp_path)]) == 4
    output = capsys.readouterr()
    result = json.loads(output.out)
    assert result["status"] == "unreadable" and result["read_only"]
    assert result["request_id"] in output.err and "agent origin marker" in output.err
    assert "Traceback" in output.err and "fake-agent-secret" not in output.err
    assert (list(parent.handlers), parent.level, parent.propagate) == before
    assert list(tmp_path.rglob("*")) == files


def test_cli_validation_failure_inside_query_keeps_original_cause(tmp_path, monkeypatch, capsys):
    from openmenu_gdemu_manager import cli
    from openmenu_gdemu_manager.services import agent_queries
    image = tmp_path / "disc.gdi"
    image.write_text("synthetic", encoding="utf-8")
    def fail(*args): raise RuntimeError("validator origin marker")
    monkeypatch.setattr(agent_queries, "validate_source", fail)
    assert cli.main(["validate-image", str(image)]) == 4
    output = capsys.readouterr()
    result = json.loads(output.out)
    assert result["request_id"] in output.err and "validator origin marker" in output.err
    assert not (tmp_path / "runtime").exists()


def test_quoted_and_json_credentials_are_redacted():
    message = 'password="fake-quoted" {"api_key": "fake-json"} client_secret=fake-client'
    masked = diagnostics.redact_diagnostics(message)
    assert "fake-quoted" not in masked and "fake-json" not in masked and "fake-client" not in masked


def test_two_live_instances_rotate_without_losing_records(log_file, tmp_path):
    # Independent live processes on Windows must not keep each other's log open.
    base = tmp_path / "concurrent" / "app.log"
    base.parent.mkdir()
    first_path = base.with_name(base.stem + "." + "a" * 32 + ".log")
    first = diagnostics.SessionFileHandler(first_path)
    first.maxBytes = 128
    code = """from pathlib import Path
import logging, sys
from openmenu_gdemu_manager.app import logger
logger.LOG_PATH = Path(sys.argv[1])
path = logger.setup_logging()
handler = next(h for h in logging.getLogger().handlers if isinstance(h, logger.SessionFileHandler))
handler.maxBytes = 512
for n in range(15): logging.getLogger('synthetic').error('second marker %s %s', n, 'x'*150)
print(path)
"""
    try:
        process = subprocess.run([sys.executable, "-c", code, str(base)], capture_output=True, text=True, timeout=20)
        assert process.returncode == 0 and "Logging error" not in process.stderr
        second_path = Path(process.stdout.strip())
        assert second_path != first_path and "second marker 14" in second_path.read_text()
        for n in range(8): first.emit(logging.LogRecord("test", logging.ERROR, __file__, 1, "first marker %s", (n,), None))
        assert "first marker 7" in first_path.read_text()
        assert "Logging error" not in process.stderr
    finally: first.close()


def test_history_pruning_keeps_live_sessions_and_removes_retired(log_file, tmp_path):
    base = tmp_path / "history" / "app.log"
    base.parent.mkdir()
    live = base.with_name(base.stem + "." + "a" * 32 + ".log")
    handler = diagnostics.SessionFileHandler(live)
    os.utime(live, (1, 1))
    retired = base.with_name(base.stem + "." + "b" * 32 + ".log")
    retired.write_text("retired")
    os.utime(retired, (2, 2))
    newer = []
    for n in range(diagnostics.SESSION_COUNT):
        path = base.with_name(base.stem + "." + format(n, "032x") + ".log")
        path.write_text("recent")
        newer.append(path)
    try:
        diagnostics._prune_sessions(base, newer[-1])
        assert live.exists() and not retired.exists() and all(p.exists() for p in newer)
    finally: handler.close()
    diagnostics._prune_sessions(base, newer[-1])
    assert not live.exists()



def test_escaped_quotes_in_credentials_do_not_leak_suffixes():
    # Serialized credentials can contain escaped quotes inside their value.
    message = json.dumps({"api_key": 'first"secret-tail'}) + r" password='quoted\'private-tail'"
    masked = diagnostics.redact_diagnostics(message)
    assert "secret-tail" not in masked and "private-tail" not in masked and "first" not in masked
