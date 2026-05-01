# Distribution

This project is intended to be distributed as a portable Windows build.

## Portable Windows build

From a clean checkout:

```powershell
py -m pip install -e ".[dev]"
py -m pytest
.\scripts\build_portable.ps1 -Version 0.1.0
```

The script creates:

- `dist/OpenMenuGDEMUManager-Portable/`
- `dist/OpenMenuGDEMUManager-<version>-portable-windows.zip`

Users should launch `Run-Portable.cmd`. That wrapper keeps settings, logs, cache, cover inbox and backups inside the portable folder instead of `%LOCALAPPDATA%`.

## Updates

The app checks the latest GitHub release on startup. If a newer version exists, it prompts the user and opens the release page so they can download the new portable ZIP.

This app does not self-replace its executable. That keeps update behavior simple and avoids writing over a running program.

## Release checklist

- Run tests on Windows.
- Build the portable ZIP.
- Create a GitHub release tagged as `vX.Y.Z`.
- Attach the portable ZIP to the release.
- Include release notes and any migration warnings.

Do not include ROMs, BIOS files, game images, SD backups, generated reports, logs, cache folders or private API credentials.
