"""Conventional Commit validator behavior, including command-line exit codes."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest

VALIDATOR = Path(__file__).resolve().parents[1] / "scripts" / "check_commit_message.py"
spec = importlib.util.spec_from_file_location("commit_message_validator", VALIDATOR)
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


@pytest.mark.parametrize("message", [
    "feat: add cover selection",
    "fix(covers): conservar la elección",
    "refactor(ui/detail)!: change session contract\n\nBREAKING CHANGE: the session API changed",
    "docs(gitflow): document develop\n\nBody with detail.\n\nRefs: #12",
    "\ufeffdocs: describe workflow\r\n\r\n# Git editor comment",
    "# Git editor comment\n\nchore: configure hooks",
    "revert(storage): undo staging change",
])
def test_valid_headers(message):
    assert validator.validate_message(message) is None


@pytest.mark.parametrize("message", [
    "", "# comment only\n", "Update docs", "Fix: change", "fix(scope):", "feat(): add", "feat:  add",
    " feat: add", "unknown: change", "feat : add", "fix: trailing ", "feat: " + "x" * 100,
])
def test_invalid_headers(message):
    assert validator.validate_message(message)


def test_cli_valid_file_and_invalid_message(tmp_path):
    message_file = tmp_path / "message with spaces.txt"
    message_file.write_text("docs(gitflow): explain promotion", encoding="utf-8-sig")
    assert subprocess.run([sys.executable, str(VALIDATOR), str(message_file)], capture_output=True).returncode == 0
    invalid = subprocess.run([sys.executable, str(VALIDATOR), "--message", "Update docs"], capture_output=True, text=True)
    assert invalid.returncode == 1
    assert "Commit rejected" in invalid.stderr


def test_cli_infrastructure_error(tmp_path):
    missing = subprocess.run([sys.executable, str(VALIDATOR), str(tmp_path / "missing.txt")], capture_output=True, text=True)
    assert missing.returncode == 2
    assert "Could not read" in missing.stderr
    assert subprocess.run([sys.executable, str(VALIDATOR)], capture_output=True).returncode == 2
