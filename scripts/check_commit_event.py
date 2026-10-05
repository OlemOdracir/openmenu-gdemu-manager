"""Read GitHub event JSON as data and validate proposed commits and PR titles."""
from __future__ import annotations

import json
from pathlib import Path
import os
import sys

from check_commit_message import check_range, validate_message


def main() -> int:
    try:
        event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
        anchor = Path("scripts/conventional_commits_base.txt").read_text().strip()
        if "pull_request" in event:
            pr = event["pull_request"]
            problems = []
            title_problem = validate_message(pr["title"], editor=False)
            if title_problem:
                problems.append("PR title: " + title_problem)
            # Check all post-policy commits in the proposed head, not GitHub's
            # synthetic refs/pull/N/merge test commit.
            problems += check_range(anchor, pr["head"]["sha"])
        elif "after" in event and set(event["after"]) != {"0"}:
            problems = check_range(anchor, event["after"])
        elif event.get("deleted"):
            problems = []
        else:
            raise ValueError("Unsupported GitHub event")
    except (KeyError, OSError, ValueError, RuntimeError) as error:
        print(f"Commit validation infrastructure error: {error}", file=sys.stderr)
        return 2
    for problem in problems:
        print(f"Commit policy rejected: {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
