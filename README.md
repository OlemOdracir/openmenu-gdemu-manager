# OpenMenu GDEMU Manager

[Español](README.es.md)

Windows desktop app for preparing and managing Dreamcast GDEMU/OpenMenu SD cards and local backups.

The app can scan a GDEMU/OpenMenu structure, stage cover art, add or remove games, and apply changes only after a safety diagnostic allows writing.

## Status

Early public beta. Use it with backups and review the diagnostic before applying changes to an SD card.

This repository does not include ROMs, BIOS files, commercial game data, SD backups, official Sega assets, or private API credentials.

## Download

Download the latest portable Windows ZIP from [GitHub Releases](https://github.com/OlemOdracir/openmenu-gdemu-manager/releases).

Extract the ZIP and run `OpenMenuGDEMUManager.exe`. The app stores settings, logs, cache and generated files in the portable `data/` folder next to the executable.

This beta is not digitally signed. Windows SmartScreen may show a warning the first time it is opened.

## Screenshots

Screenshots will be added before the public beta announcement.

## License

OpenMenu GDEMU Manager is licensed under the GNU General Public License v3.0 or later. See [LICENSE](LICENSE).

## Run From Source

Requirements:

- Windows
- Python 3.11 or newer

```powershell
py -m pip install -e ".[dev]"
py -m openmenu_gdemu_manager
```

For local development:

```powershell
py -m pytest
```

## Portable Windows Build

To create a portable build:

```powershell
.\scripts\build_portable.ps1 -Version 0.1.0
```

The output is written to `dist/`:

- `OpenMenuGDEMUManager-Portable/`
- `OpenMenuGDEMUManager-0.1.0-portable-windows.zip`

Portable users should run `OpenMenuGDEMUManager.exe`. The executable keeps settings, logs, cache and generated files inside the portable folder.

## Updates

On startup, the app checks the latest GitHub release. If a newer version is available, it shows a prompt and opens the release page so the user can download the new portable ZIP.

The app does not overwrite or self-replace its executable.

## Safe Diagnostics

Before scanning or writing, the selected path is classified. Write actions are enabled only for a compatible OpenMenu/GDEMU structure or a local backup that passes validation.

The app blocks writing for:

- internal drive roots
- paths that do not look like GDEMU/OpenMenu storage
- removable drives that are not FAT32
- paths with possible corruption markers

The app does not format drives, repair filesystems, or run `chkdsk`.

## OpenMenu Base Template

The optional "Install OpenMenu base" action expects a user-provided template folder configured in settings. By default it looks for:

```text
_OpenMenuBuild/01
```

That folder is intentionally not included in the public repository. Only use files you are allowed to distribute or copy.

## Cover Sources

Default safe sources are local folders, openMenu image DB data, Libretro thumbnails, and the OpenMenu Cover API proxy. The proxy does not require user accounts and does not expose third-party developer credentials to the desktop app.

Advanced direct providers such as ScreenScraper can be configured locally by users who want to use their own credentials. Other API providers are reserved for future versions.

Manual Google/Bing/DuckDuckGo image searches open in the browser. The app does not scrape those sites automatically.

## Runtime Data

Runtime data is kept outside the repo by default, under the app data directory, or inside the portable folder when using the portable executable.

Common generated files include:

- settings: `cover_sources.json`
- state: `_cover_manager_state.json`
- logs: `openmenu_gdemu_manager.log`
- staged covers: `_cover_inbox/`
- reports: `cover_report.tsv`, `cover_report.json`

These files should not be committed.

## Third-party Notices

See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Contact

Project contact: openmenu.gdemu.manager@gmail.com
