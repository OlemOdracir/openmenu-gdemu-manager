# Basic Gitflow and Conventional Commits

## Branches

- `main` contains stable, validated versions. Keep it as the public default branch.
- `develop` integrates ongoing work. Small, focused changes may be committed here; larger work uses `feature/<topic>` or `fix/<topic>` from `develop` and returns through a pull request targeting `develop`.
- Promote `develop` to `main` through a pull request when the release checklist and required validation are satisfied. A prototype commit or a green unit test is not a release or a hardware validation.
- An urgent fix starts in `hotfix/<topic>` from `main`, returns through a pull request to `main`, and is then merged back into `develop`.
- `release/*` branches are optional: create one only when stabilizing a release while new development continues.

Do not rewrite existing public history to change old commit messages. **Every new commit must use the convention below**, including merge, squash, revert, bot and release commits. There are no generated-merge exceptions. Raw `Merge ...`, `Revert ...`, `fixup! ...` and `squash! ...` messages are rejected; autosquash work must be completed before publishing. A PR title must also follow the convention.

Branches and draft pull requests in this public repository are also public. A branch does not change the content rules in CONTRIBUTING. Local edits are not saved in Git history until committed; a local commit has no remote backup until pushed.

## Commit messages

Use Conventional Commits 1.0.0:

```text
<type>(optional-scope)[optional !]: <description>
```

Project types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`. Scope is optional; use a short component name such as `ux`, `covers`, `storage` or `gitflow`. Write a clear description, keep the header at most 100 characters, and explain significant changes in the body. Use `!` or a `BREAKING CHANGE:` footer for incompatible behavior. Header validation does not decide semantic versioning or verify the correctness of a breaking-change claim.

Examples:

```text
docs(gitflow): document develop and main workflow
feat(ux): add cover comparison controls
fix(covers): preserve chosen image after search failure
test(storage): reject an incomplete GDI source
```

## Local validation

The versioned `scripts/git-hooks/commit-msg` hook blocks invalid messages. `pre-push` checks every post-policy commit in outgoing branches/tags, including merge commits and commits created with creation hooks bypassed. The standard-library-only scripts under `scripts/check_commit_*.py` provide these checks; they do not run product code or modify commit history.

Enable it once in each clone:

```powershell
git config --local core.hooksPath scripts/git-hooks
```

The hook uses the project's `.venv` Python when runnable, then the Windows Python launcher or a Python interpreter in PATH. It probes each interpreter and requires Python 3.11+, so a stale/broken virtual environment does not prevent fallback. If no interpreter is usable it stops with an actionable error. If an existing clone already uses custom hooks, integrate the validator with them rather than replacing that hook configuration blindly.

Check a proposed header or message file directly:

```powershell
py scripts/check_commit_message.py --message "docs(ux): describe prototype navigation"
py scripts/check_commit_message.py .git/COMMIT_EDITMSG
py scripts/check_commit_message.py --range main develop
py -m pytest tests/test_commit_message.py tests/test_commit_policy.py
```

The existing public history up to the commit recorded in `scripts/conventional_commits_base.txt` is grandfathered. The pre-push and CI validators check every reachable commit after that anchor, including commits already pushed on another branch; promotion to main does not exempt their messages. Do not advance this anchor to hide a violation. An invalid or missing anchor fails validation. No history was rewritten.

## CI and actual enforcement status

`.github/workflows/conventional-commits.yml` checks pushes and pull requests, including PR title edits. It reads event JSON as data, never inserts untrusted titles/messages into shell commands, and checks the PR head rather than GitHub's synthetic test merge. It needs only read permissions, full Git history and Python 3.12. The standard library scripts use no added Python dependency. Checkout v4 (`11d5960a326750d5838078e36cf38b85af677262`) and setup-python v5 (`a26af69be951a213d495a4c3e4e4022e16d87065`) are pinned upstream GitHub Actions (MIT; see their upstream LICENSE files). Review these pins before changing versions.

**Current status, 5 October 2026:** local hooks are enabled in the working clone. The CI file is prepared locally and will run once published to GitHub; no push is implied by this document. CI reports violations but cannot itself prevent direct pushes or user-edited GitHub merge messages. Hooks can be bypassed with `--no-verify` or disabled, so they do not establish a repository-wide guarantee across all clients.

An attempted repository ruleset with `commit_message_pattern` was rejected by GitHub (HTTP 422, invalid rule). [GitHub documents commit metadata restrictions for organizations on Enterprise](https://docs.github.com/en/enterprise-cloud@latest/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets#metadata-restrictions). No server rule was activated. `scripts/conventional-commits.ruleset.json` is an **unapplied template**, not evidence of protection. If that capability becomes available, test/import it, verify its active state and keep its bypass list empty. The template applies to all branches and has no merge or bot exceptions.

With the present repository, requiring the `Conventional Commits` check on PRs into main/develop is an alternative integration gate. It would require topic branches/PRs instead of direct develop pushes, publishing the workflow first, and configuring branch rules. That workflow change and protection are **not active**. A required PR check still cannot validate an edited final merge message by itself. Keep this limitation visible until a server-level solution is agreed and verified.

## Daily work and promotion

Before switching branches, inspect the working tree. Do not discard another task's pending files or include them in a focused commit.

```powershell
git status --short
git switch develop
# Make and validate a focused change.
git add <explicit-paths>
git commit -m "fix(covers): preserve search context"
# After reviewing the exact outgoing files and commits:
git push -u origin develop
```

Large features start with the scope issue required by CONTRIBUTING, then a topic branch:

```powershell
git switch develop
git switch -c feature/cover-detail
```

Use a PR with base `develop` for that feature. Use a PR with base `main` and compare `develop` for a stable release. Keep the release commit history when promoting an integration branch (a merge commit rather than repeatedly squashing the entire develop history), and synchronize `main` back into `develop` afterward. Give the final merge message a conventional header, for example `chore(release): merge develop into main`. On GitHub, review and edit the final message before merging; a conventional PR title alone does not validate the final merge commit. Raw automatic merge messages are not allowed by this project's policy.

Release requirements remain in [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md) and [../AGENTS.md](../AGENTS.md): tests, portable build, clean Windows environment and physical SD/Dreamcast checks. An unavailable check remains pending.

## UX prototype checkpoint

The current HTML prototype is maintained outside this checkout. Its local backup preserves the work. Adding it to this repository is a separate reviewed change under `docs/ux/prototype/`, with publication-ready assets, relative documentation links and the i18n requirements in AGENTS. Do not commit the cached cover images, generated HTML containing them, local backups, personal paths or run traces. Creating `develop` does not automatically import or publish that prototype.

References: [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/), [GitHub pull request workflow](https://docs.github.com/en/pull-requests/get-started/pull-request-quickstart).
