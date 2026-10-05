"""Validate the project's Conventional Commit header; no third-party dependencies."""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys
import subprocess

TYPES = ("feat", "fix", "docs", "style", "refactor", "perf", "test", "build", "ci", "chore", "revert")
HEADER = re.compile(r"^(?:" + "|".join(TYPES) + r")(?:\([A-Za-z0-9][A-Za-z0-9._/-]*\))?!?: \S(?:.*\S)?$")


def validate_message(message: str, *, editor: bool = True) -> str | None:
    """Return an actionable error, or None for a valid authored commit header."""
    lines = (message.lstrip("\ufeff") if editor else message).splitlines()
    header = next((line for line in lines if line.strip() and not line.startswith("#")), "") if editor else (lines[0] if lines else "")
    if not header:
        return "The commit message is empty."
    if len(header) > 100:
        return "Keep the commit header at most 100 characters; put details in the body."
    if not HEADER.fullmatch(header):
        return "Use <type>(optional-scope): <description>, for example: docs(gitflow): describe develop workflow. Types: " + ", ".join(TYPES) + ". Use ! before : for a breaking change."
    return None


def git(*args: str, cwd: str | None = None) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, text=True, encoding="utf-8", errors="replace", capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "Git command failed")
    return result.stdout.rstrip("\n")


def check_range(base: str, head: str, *, cwd: str | None = None) -> list[str]:
    """Validate every introduced commit, including merges; never rewrite history."""
    # Resolve first. Refs cannot inject options into rev-list or shell commands.
    base_sha = git("rev-parse", "--verify", "--end-of-options", base + "^{commit}", cwd=cwd)
    head_sha = git("rev-parse", "--verify", "--end-of-options", head + "^{commit}", cwd=cwd)
    problems = []
    for commit in git("rev-list", head_sha, "^" + base_sha, cwd=cwd).splitlines():
        problem = validate_message(git("show", "-s", "--format=%B", commit, cwd=cwd), editor=False)
        if problem:
            problems.append(f"{commit[:12]}: {problem}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("message_file", nargs="?", help="Git commit message file")
    parser.add_argument("--message", help="Validate a message supplied directly")
    parser.add_argument("--range", nargs=2, metavar=("BASE", "HEAD"), help="Check every commit reachable from HEAD but not BASE, including merges")
    args = parser.parse_args(argv)
    if sum([bool(args.message_file), args.message is not None, args.range is not None]) != 1:
        parser.error("provide a message file, --message or --range BASE HEAD")
    if args.range:
        try:
            problems = check_range(*args.range)
        except (OSError, RuntimeError) as error:
            print(f"Commit range could not be checked: {error}", file=sys.stderr)
            return 2
        for problem in problems:
            print(f"Commit rejected: {problem}", file=sys.stderr)
        return 1 if problems else 0
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
