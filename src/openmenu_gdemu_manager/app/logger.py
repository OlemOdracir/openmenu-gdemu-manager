"""Bounded desktop diagnostics and stderr-only agent diagnostics (no Qt import)."""
import contextvars
import functools
import logging
from logging.handlers import RotatingFileHandler
import platform
import os
import re
import sys
import tempfile
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from .. import __version__
from ..config.paths import LOG_PATH

MAX_LOG_BYTES = 2 * 1024 * 1024
BACKUP_COUNT = 4
SESSION_COUNT = 5
_active_log_path = LOG_PATH
_context = contextvars.ContextVar("logging_operation", default=("-", "-"))
AGENT_LOGGER = "openmenu_gdemu_manager.agent"
# Library calls do not configure the host application's logging or create files.
logging.getLogger(AGENT_LOGGER).addHandler(logging.NullHandler())


def redact_diagnostics(text):
    """Mask known credential fields, URL userinfo and bearer headers, not all PII."""
    text = re.sub(r"(?i)(https?://)[^\s/@]+@", r"\1[redacted]@", text)
    text = re.sub(r"(?i)(authorization\s*[:=]\s*(?:bearer|basic)\s+)[^\s,;]+", r"\1[redacted]", text)
    # Query parameters and common JSON/dict/key=value exception representations.
    return re.sub(
        r"(?i)((?:[?&]|\b)(?:devpassword|sspassword|password|passwd|token|access_token|api[_-]?key|client_secret|secret)[\"']?\s*[:=]\s*)"
        r"(?:\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|[^&\s\"'<>},;]+)",
        r"\1[redacted]", text,
    )


def _lock_lease(handle):
    handle.seek(0)
    if os.name == "nt":
        import msvcrt
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


class SessionFileHandler(RotatingFileHandler):
    """Each process owns a unique file and a lease until its handler closes."""
    def __init__(self, path):
        self.lease = open(str(path) + ".lock", "a+b")
        try:
            if self.lease.seek(0, 2) == 0:
                self.lease.write(b"1")
                self.lease.flush()
            _lock_lease(self.lease)
            super().__init__(path, maxBytes=MAX_LOG_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8")
        except Exception:
            self.lease.close()
            raise

    def close(self):
        try:
            super().close()
        finally:
            if hasattr(self, "lease"): self.lease.close()


def _prune_sessions(base_path, current_path):
    pattern = re.compile(re.escape(base_path.stem) + r"\.[a-f0-9]{32}\.log$")
    sessions = [p for p in base_path.parent.iterdir() if pattern.fullmatch(p.name) and not p.is_symlink()]
    sessions.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    for path in sessions[SESSION_COUNT:]:
        if path == current_path: continue
        lease_path = Path(str(path) + ".lock")
        if lease_path.is_symlink(): continue
        # A crashed session's lease is released by the OS. Active logs are never
        # deleted, even when there are more than SESSION_COUNT application instances.
        try:
            with lease_path.open("a+b") as lease:
                _lock_lease(lease)
                for item in [path, *[Path(str(path) + "." + str(n)) for n in range(1, BACKUP_COUNT + 1)]]:
                    item.unlink(missing_ok=True)
            lease_path.unlink(missing_ok=True)
        except OSError:
            continue


class DiagnosticFormatter(logging.Formatter):
    converter = time.gmtime

    def format(self, record):
        return redact_diagnostics(super().format(record))


class DiagnosticContext(logging.Filter):
    def __init__(self, session_id):
        super().__init__()
        self.session_id = session_id

    def filter(self, record):
        record.session_id = self.session_id
        operation, operation_id = _context.get()
        if not hasattr(record, "operation"): record.operation = operation
        if not hasattr(record, "operation_id"): record.operation_id = operation_id
        return True


@contextmanager
def operation_context(operation, operation_id=None):
    operation_id = operation_id or (_context.get()[1] if _context.get()[1] != "-" else uuid.uuid4().hex)
    token = _context.set((operation, operation_id))
    try:
        yield operation_id
    finally:
        _context.reset(token)


def logged_operation(operation):
    def decorate(function):
        @functools.wraps(function)
        def wrapped(*args, **kwargs):
            with operation_context(operation):
                return function(*args, **kwargs)
        return wrapped
    return decorate


def _configure_handler(handler, session_id):
    handler.setFormatter(DiagnosticFormatter(
        "%(asctime)sZ %(levelname)s %(name)s session=%(session_id)s "
        "thread=%(threadName)s operation=%(operation)s operation_id=%(operation_id)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    ))
    handler.addFilter(DiagnosticContext(session_id))
    return handler


def active_log_path():
    return _active_log_path


def setup_logging():
    global _active_log_path
    session_id = uuid.uuid4().hex
    base_path = LOG_PATH
    path = base_path.with_name(f"{base_path.stem}.{session_id}.log")
    fallback_error = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = SessionFileHandler(path)
    except OSError as exc:
        fallback_error = exc
        base_path = Path(tempfile.gettempdir()) / "OpenMenu GDEMU Manager" / LOG_PATH.name
        path = base_path.with_name(f"{base_path.stem}.{session_id}.log")
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = SessionFileHandler(path)
    _active_log_path = path
    handlers = [_configure_handler(file_handler, session_id)]
    if sys.stderr is not None:
        handlers.append(_configure_handler(logging.StreamHandler(sys.stderr), session_id))
    logging.basicConfig(level=logging.INFO, handlers=handlers, force=True)
    sys.excepthook = log_uncaught_exception
    threading.excepthook = log_thread_exception
    log = logging.getLogger(__name__)
    log.info("Session started: app=%s Python=%s platform=%s frozen=%s log=%s",
             __version__, platform.python_version(), platform.platform(), getattr(sys, "frozen", False), path)
    if fallback_error:
        log.warning("Runtime log unavailable; using temporary log: %s; reason=%s", path, fallback_error)
    try:
        _prune_sessions(base_path, path)
    except OSError:
        log.warning("Could not prune retired diagnostic sessions", exc_info=True)
    return path


@contextmanager
def agent_logging():
    """No file, migration or GUI; restore host logging after the command."""
    request_id = uuid.uuid4().hex
    log = logging.getLogger(AGENT_LOGGER)
    previous = (list(log.handlers), log.level, log.propagate)
    handler = (_configure_handler(logging.StreamHandler(sys.stderr), request_id)
               if sys.stderr is not None else logging.NullHandler())
    log.handlers = [handler]
    log.setLevel(logging.INFO)
    log.propagate = False
    try:
        yield request_id
    finally:
        log.handlers, level, log.propagate = previous
        log.setLevel(level)
        handler.close()


def log_uncaught_exception(exc_type, exc_value, exc_traceback):
    logging.getLogger("uncaught").critical(
        "Unhandled exception", exc_info=(exc_type, exc_value, exc_traceback))


def log_thread_exception(args):
    if args.exc_type is SystemExit:
        return
    logging.getLogger("uncaught.thread").critical(
        "Unhandled worker thread exception: %s", getattr(args.thread, "name", "unknown"),
        exc_info=(args.exc_type, args.exc_value, args.exc_traceback))


def install_qt_logging():
    # Called only after logging is active and the desktop dependency loaded.
    from PySide6.QtCore import QtMsgType, qInstallMessageHandler, qVersion
    levels = {QtMsgType.QtDebugMsg: logging.DEBUG, QtMsgType.QtInfoMsg: logging.INFO,
              QtMsgType.QtWarningMsg: logging.WARNING, QtMsgType.QtCriticalMsg: logging.ERROR,
              QtMsgType.QtFatalMsg: logging.CRITICAL}
    def qt_message(kind, context, message):
        logging.getLogger("qt").log(levels.get(kind, logging.WARNING), "%s [%s:%s]", message, context.file or "", context.line)
    previous = qInstallMessageHandler(qt_message)
    logging.getLogger(__name__).info("Qt initialized: version=%s", qVersion())
    return previous
