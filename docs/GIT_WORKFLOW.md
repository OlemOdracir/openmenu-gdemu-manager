# Basic Gitflow and Conventional Commits

## Branches

- `main` contains stable, validated versions. Keep it as the public default branch.
- `develop` integrates ongoing work. Small, focused changes may be committed here; larger work uses `feature/<topic>` or `fix/<topic>` from `develop` and returns through a pull request targeting `develop`.
- Promote `develop` to `main` through a pull request when the release checklist and required validation are satisfied. A prototype commit or a green unit test is not a release or a hardware validation.
- An urgent fix starts in `hotfix/<topic>` from `main`, returns through a pull request to `main`, and is then merged back into `develop`.
- `release/*` branches are optional: create one only when stabilizing a release while new development continues.

Do not rewrite existing public history to change old commit messages. All new manually authored commits use the convention below. Generated GitHub merge commits are structural history; the pull request title and authored commits must carry the intended Conventional Commit message.

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

The versioned `scripts/git-hooks/commit-msg` hook checks new commit headers using the standard-library-only `scripts/check_commit_message.py`.

Enable it once in each clone:

```powershell
git config --local core.hooksPath scripts/git-hooks
```

The hook uses the project's `.venv` Python when runnable, then the Windows Python launcher or a Python interpreter in PATH. It probes each interpreter and requires Python 3.11+, so a stale/broken virtual environment does not prevent fallback. If no interpreter is usable it stops with an actionable error. If an existing clone already uses custom hooks, integrate the validator with them rather than replacing that hook configuration blindly.

Check a proposed header or message file directly:

```powershell
py scripts/check_commit_message.py --message "docs(ux): describe prototype navigation"
py scripts/check_commit_message.py .git/COMMIT_EDITMSG
py -m pytest tests/test_commit_message.py
```

This is a local convenience, not server-side enforcement: hooks can be bypassed and each clone must enable them. Recommended GitHub protections for `main` are pull requests, no force pushes/deletion and required relevant checks. Those settings require separate configuration on GitHub; this document does not imply they have been enabled. PR-title/commit validation in CI can be added when the team needs enforcement across all clients.

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

Use a PR with base `develop` for that feature. Use a PR with base `main` and compare `develop` for a stable release. Keep the release commit history when promoting an integration branch (a merge commit rather than repeatedly squashing the entire develop history), and synchronize `main` back into `develop` afterward. If doing an authorized local merge, give its message a conventional header, for example `chore(release): merge develop into main`.

Release requirements remain in [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md) and [../AGENTS.md](../AGENTS.md): tests, portable build, clean Windows environment and physical SD/Dreamcast checks. An unavailable check remains pending.

## UX prototype checkpoint

The current HTML prototype is maintained outside this checkout. Its local backup preserves the work. Adding it to this repository is a separate reviewed change under `docs/ux/prototype/`, with publication-ready assets, relative documentation links and the i18n requirements in AGENTS. Do not commit the cached cover images, generated HTML containing them, local backups, personal paths or run traces. Creating `develop` does not automatically import or publish that prototype.

References: [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/), [GitHub pull request workflow](https://docs.github.com/en/pull-requests/get-started/pull-request-quickstart).
