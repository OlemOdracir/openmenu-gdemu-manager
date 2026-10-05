"""Validate the project's Conventional Commit header; no third-party dependencies."""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

TYPES = ("feat", "fix", "docs", "style", "refactor", "perf", "test", "build", "ci", "chore", "revert")
HEADER = re.compile(r"^(?:" + "|".join(TYPES) + r")(?:\([A-Za-z0-9][A-Za-z0-9._/-]*\))?!?: \S(?:.*\S)?$")


def validate_message(message: str) -> str | None:
    """Return an actionable error, or None for a valid authored commit header."""
    lines = message.lstrip("\ufeff").splitlines()
    header = next((line for line in lines if line.strip() and not line.startswith("#")), "")
    if not header:
        return "The commit message is empty."
    if len(header) > 100:
        return "Keep the commit header at most 100 characters; put details in the body."
    if not HEADER.fullmatch(header):
        return "Use <type>(optional-scope): <description>, for example: docs(gitflow): describe develop workflow. Types: " + ", ".join(TYPES) + ". Use ! before : for a breaking change."
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("message_file", nargs="?", help="Git commit message file")
    parser.add_argument("--message", help="Validate a message supplied directly")
    args = parser.parse_args(argv)
    if bool(args.message_file) == (args.message is not None):
        parser.error("provide either a message file or --message")
    try:
        message = args.message if args.message is not None else Path(args.message_file).read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as error:
        print(f"Could not read the commit message: {error}", file=sys.stderr)
        return 2
    problem = validate_message(message)
    if problem:
        print(f"Commit rejected: {problem}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
