"""Validate every newly pushed commit, including commits created with hooks bypassed."""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

from check_commit_message import git, validate_message

SHA = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")


def check_updates(lines: list[str], repo: str) -> list[str]:
    # Grandfather only the explicitly recorded existing public history, not all
    # remote refs (which might already contain an invalid new commit).
    anchor = (Path(repo) / "scripts/conventional_commits_base.txt").read_text(encoding="utf-8").strip()
    git("rev-parse", "--verify", "--end-of-options", anchor + "^{commit}", cwd=repo)
    problems = []
    checked = set()
    for line in lines:
        fields = line.split()
        if len(fields) != 4:
            raise ValueError("Invalid pre-push input")
        _, local_sha, remote_ref, remote_sha = fields
        if not SHA.fullmatch(local_sha) or not SHA.fullmatch(remote_sha):
            raise ValueError("Invalid pre-push object ID")
        if set(local_sha) == {"0"}:  # deletion introduces no commits
            continue
        # Include commits already on another branch: all post-policy messages
        # must comply even when promoting develop or creating a new branch/tag.
        commits = git("rev-list", local_sha, "^" + anchor, cwd=repo).splitlines()
        for commit in commits:
            if commit in checked:
                continue
            checked.add(commit)
            problem = validate_message(git("show", "-s", "--format=%B", commit, cwd=repo), editor=False)
            if problem:
                problems.append(f"{remote_ref}: {commit[:12]}: {problem}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".")
    args = parser.parse_args()
    try:
        problems = check_updates(sys.stdin.read().splitlines(), args.repo)
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Push could not be validated: {error}", file=sys.stderr)
        return 2
    for problem in problems:
        print(f"Push rejected: {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
