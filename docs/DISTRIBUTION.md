# Distribution

This project is intended to be distributed as a portable Windows build.

## Portable Windows build

From a clean checkout:

```powershell
py -m pip install -e ".[dev]"
py -m pytest
$Version = "0.2.0-beta.1"
.\scripts\build_portable.ps1 -Version $Version
```

The script creates:

- `dist/OpenMenuGDEMUManager-Portable/`
- `dist/OpenMenuGDEMUManager-<version>-portable-windows.zip`

Users should launch `OpenMenuGDEMUManager.exe`. The portable executable keeps settings, logs, cache, cover inbox and backups inside the portable folder instead of `%LOCALAPPDATA%`.

## Release candidate workflow

For a public beta, prefer a prerelease tag such as `v0.2.0-beta.1`.

Before publishing:

- run normal tests with no network dependency;
- run public Cover API integration tests only when the API or cover provider behavior changed;
- build the portable ZIP from a clean checkout;
- test the ZIP in a clean Windows VM with no Python installed;
- test at least one real SD workflow: scan, save covers, add/remove games, rebuild OpenMenu and rescan.

## Bundled rebuild tool

OpenMenu rebuilds use the bundled `buildgdi.exe` tool from GDIbuilder. Keep the binary, expected version and notices aligned:

- `third_party/buildgdi/buildgdi.exe`
- `THIRD_PARTY_NOTICES.md`
- `src/openmenu_gdemu_manager/config/settings.py`

Do not replace this binary silently. Any upgrade should be tested on a real SD before a public release.

## Updates

The app checks the latest GitHub release on startup. If a newer version exists, it prompts the user and opens the release page so they can download the new portable ZIP.

This app does not self-replace its executable. That keeps update behavior simple and avoids writing over a running program.

## Release checklist

- Run tests on Windows.
- Build the portable ZIP.
- Create a GitHub release tagged as `vX.Y.Z`.
- Attach the portable ZIP to the release.
- Attach the generated `.sha256.txt` file.
- Include release notes and any migration warnings.
- Mark beta builds as prerelease.

Do not include ROMs, BIOS files, game images, SD backups, generated reports, logs, cache folders or private API credentials.
