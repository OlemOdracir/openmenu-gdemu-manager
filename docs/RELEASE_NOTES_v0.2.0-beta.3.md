# OpenMenu GDEMU Manager v0.2.0-beta.3

Public beta update focused on compatibility with older SD layouts, safer game imports from backups, and clearer pre-release behavior.

## Highlights

- Detect old GDEMU/GDMenu menu folders and offer an explicit update path to the current bundled OpenMenu base.
- Keep backup optional, but show backup first when an old menu needs migration.
- Preserve game folders `02..127` while replacing only menu folder `01` during legacy menu update.
- Improve game name detection when folder names are numeric or generic by reading CDI/GDI metadata and internal disc titles.
- Ignore menu folder `01` when adding games from an SD backup, so only real GDI/CDI games are listed.
- Make the Add Games review table read-only and show shorter, clearer source paths.
- Keep full source paths available as tooltips in the Add Games dialog.
- Improve diagnostics for old menus and incompatible menu states.

## Safety

- The app still does not format SD cards.
- Old-menu migration requires an explicit user decision.
- Full SD backup remains optional, but recommended before changing an old menu or performing large operations.
- Removed games still go to `_openmenu_gdemu_manager/trash/`.
- Menu rebuild operations continue to use `buildgdi.exe` and avoid in-place `track05.iso` patching.

## Validation

- `uv run pytest`: 172 passed, 2 skipped.
- `.\scripts\test_release.ps1 -Version 0.2.0-beta.3`: portable build and smoke test passed.
- Portable ZIP: `OpenMenuGDEMUManager-0.2.0-beta.3-portable-windows.zip`
- SHA256: `6F539CEB5FF9A5BB77C4942EF27213394705B3D677839D18F2BE64BE0730F7FD`

## Known Limits

- The app is unsigned; Windows SmartScreen may warn on first launch.
- The app does not include games, BIOS, commercial game data or SD images.
- This remains a public beta. Keep a separate copy of important SD contents before large changes.
