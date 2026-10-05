# Contributing

Thanks for helping improve OpenMenu GDEMU Manager.

## Rules

- Follow [Basic Gitflow and Conventional Commits](docs/GIT_WORKFLOW.md): work in `develop`, use topic branches for larger changes, and promote validated releases to `main` through a pull request.
- Use Conventional Commit headers for every new commit and PR title, including merges, squashes, reverts and bots; no automatic-message exception. Enable both versioned hooks (`git config --local core.hooksPath scripts/git-hooks`) and run `py -m pytest tests/test_commit_message.py tests/test_commit_policy.py`. Existing custom hooks should be integrated rather than overwritten. See the workflow document for CI and server enforcement status.

- Use pull requests.
- Keep changes focused and easy to review.
- Follow `AGENTS.md` rules for SD safety, rebuild flow, and release checks.
- Run tests before opening a PR:

```powershell
py -m pytest
```

- Do not include ROMs, BIOS files, copyrighted game content, SD backups, logs, cache files or credentials.
- Do not add ScreenScraper or other private API credentials to the repository.
- Contributions are licensed under GPL-3.0-or-later.

## Larger changes

Open an issue first for large UI changes, architecture changes, release workflow changes, or anything that modifies SD write behavior.

## Safety-sensitive code

Changes that affect path validation, backups or SD write operations require extra care. Explain the risk and include tests.

## Languages

Issues and pull requests are welcome in English or Spanish.
