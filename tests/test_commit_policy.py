"""Real temporary Git histories; no product, network or SD operations."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import shutil

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from check_commit_message import check_range, validate_message
from check_commit_push import check_updates


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


@pytest.fixture
def history(tmp_path):
    repo = tmp_path / "git repository with spaces"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.email", "fixture@example.invalid")
    git(repo, "config", "user.name", "Test fixture")
    git(repo, "config", "core.hooksPath", str(tmp_path / "disabled-hooks"))
    git(repo, "commit", "--allow-empty", "-m", "Legacy non-conventional commit")
    anchor = git(repo, "rev-parse", "HEAD")
    (repo / "scripts").mkdir()
    (repo / "scripts/conventional_commits_base.txt").write_text(anchor)
    return repo, anchor


@pytest.mark.parametrize("message", ["Merge branch 'develop'", "Revert \"old\"", "fixup! feat: add", "squash! fix: repair", "# comment\nfix: hidden", "\nfix: hidden", "fix: trailing ", "\ufefffix: hidden"])
def test_no_merge_revert_fixup_or_committed_comment_exception(message):
    assert validate_message(message, editor=False)


def test_actual_range_checks_every_commit_and_preserves_legacy(history):
    repo, anchor = history
    git(repo, "commit", "--allow-empty", "-m", "fix: valid")
    assert check_range(anchor, "HEAD", cwd=str(repo)) == []
    git(repo, "commit", "--allow-empty", "-m", "Not conventional")
    invalid = git(repo, "rev-parse", "HEAD")
    git(repo, "commit", "--allow-empty", "-m", "docs: valid tip")
    assert any(invalid[:12] in problem for problem in check_range(anchor, "HEAD", cwd=str(repo)))


def test_real_merge_commit_is_checked(history):
    repo, anchor = history
    git(repo, "switch", "-c", "feature/test")
    git(repo, "commit", "--allow-empty", "-m", "feat: branch work")
    git(repo, "switch", "main")
    git(repo, "commit", "--allow-empty", "-m", "docs: integration work")
    git(repo, "merge", "--no-ff", "feature/test", "-m", "Merge feature")
    assert len(check_range(anchor, "HEAD", cwd=str(repo))) == 1
    git(repo, "commit", "--amend", "--no-edit", "-m", "chore: merge feature")
    assert check_range(anchor, "HEAD", cwd=str(repo)) == []


def test_push_checks_new_branch_and_existing_branch_even_if_hook_was_bypassed(history):
    repo, anchor = history
    git(repo, "commit", "--allow-empty", "-m", "Non-conventional")
    head = git(repo, "rev-parse", "HEAD")
    assert check_updates([f"refs/heads/new {head} refs/heads/new {'0'*40}"], str(repo))
    assert check_updates([f"refs/heads/main {head} refs/heads/main {anchor}"], str(repo))
    assert check_updates([f"(delete) {'0'*40} refs/heads/main {anchor}"], str(repo)) == []


def test_push_valid_all_and_invalid_input_fail_closed(history):
    repo, anchor = history
    git(repo, "commit", "--allow-empty", "-m", "chore: valid update")
    head = git(repo, "rev-parse", "HEAD")
    assert check_updates([f"refs/heads/main {head} refs/heads/main {anchor}"], str(repo)) == []
    with pytest.raises(ValueError):
        check_updates(["bad input"], str(repo))
    with pytest.raises(RuntimeError):
        check_range("--all", "HEAD", cwd=str(repo))


def test_cli_range_infrastructure_and_invalid_exit(history):
    repo, anchor = history
    git(repo, "commit", "--allow-empty", "-m", "Invalid")
    run = lambda base: subprocess.run([sys.executable, str(SCRIPTS / "check_commit_message.py"), "--range", base, "HEAD"], cwd=repo, capture_output=True)
    assert run(anchor).returncode == 1
    assert run("missing-ref").returncode == 2


def test_github_pr_title_is_data_and_synthetic_merge_is_not_checked(history, monkeypatch, capsys):
    import check_commit_event
    repo, _ = history
    git(repo, "commit", "--allow-empty", "-m", "feat: proper work")
    event_file = repo / "event.json"
    event = {"pull_request": {"title": "Invalid title", "head": {"sha": git(repo, "rev-parse", "HEAD")}}}
    event_file.write_text(json.dumps(event))
    monkeypatch.chdir(repo)
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_file))
    assert check_commit_event.main() == 1
    event["pull_request"]["title"] = "feat: safe $(never-execute) `literal`"
    event_file.write_text(json.dumps(event))
    assert check_commit_event.main() == 0
    git(repo, "commit", "--allow-empty", "-m", "Merge pull request #1")
    assert check_commit_event.main() == 0  # checks event head, not checkout merge HEAD


def test_github_push_unknown_or_invalid_event_fails_closed(history, monkeypatch):
    import check_commit_event
    repo, _ = history
    git(repo, "commit", "--allow-empty", "-m", "Invalid pushed commit")
    file = repo / "event.json"
    monkeypatch.chdir(repo)
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(file))
    file.write_text(json.dumps({"after": git(repo, "rev-parse", "HEAD")}))
    assert check_commit_event.main() == 1
    file.write_text("{}")
    assert check_commit_event.main() == 2


def test_real_hooks_reject_creation_and_push_to_local_bare_repository(history, tmp_path):
    repo, anchor = history
    for name in ["check_commit_message.py", "check_commit_push.py"]:
        shutil.copy2(SCRIPTS / name, repo / "scripts" / name)
    hook_dir = repo / "scripts/git-hooks"
    hook_dir.mkdir()
    for name in ["commit-msg", "pre-push"]:
        shutil.copy2(SCRIPTS / "git-hooks" / name, hook_dir / name)
        (hook_dir / name).chmod(0o755)
    git(repo, "config", "core.hooksPath", str(hook_dir))
    bad = subprocess.run(["git", "-C", str(repo), "commit", "--allow-empty", "-m", "Invalid header"], capture_output=True)
    assert bad.returncode != 0
    assert git(repo, "rev-parse", "HEAD") == anchor
    git(repo, "-c", "core.hooksPath=" + str(tmp_path / "disabled-hooks"), "commit", "--allow-empty", "-m", "Bypassed creation hook")
    remote = tmp_path / "local remote.git"
    subprocess.check_call(["git", "init", "--bare", str(remote)], stdout=subprocess.DEVNULL)
    rejected = subprocess.run(["git", "-C", str(repo), "push", str(remote), "HEAD:refs/heads/develop"], capture_output=True, text=True)
    assert rejected.returncode != 0
    assert "Push rejected" in rejected.stderr
    assert git(remote, "for-each-ref", "--format=%(refname)") == ""
    git(repo, "commit", "--amend", "--allow-empty", "-m", "test(gitflow): conventional header")
    git(repo, "push", str(remote), "HEAD:refs/heads/develop")
    assert git(remote, "rev-parse", "refs/heads/develop") == git(repo, "rev-parse", "HEAD")
