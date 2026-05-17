# Contributing

Thanks for helping improve OpenMenu GDEMU Manager.

## Rules

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
