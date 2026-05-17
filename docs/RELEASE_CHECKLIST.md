# Release checklist

## Before building

- Confirm the repository is clean: `git status --short`.
- Confirm no credentials, ROMs, BIOS files, SD backups, logs or cache files are staged.
- Run unit tests: `py -m pytest`.
- Confirm the app version and build version match the intended tag.
- Confirm `THIRD_PARTY_NOTICES.md` still covers bundled tools and assets.
- Run public API integration tests when the API changed:

```powershell
$env:OPENMENU_RUN_INTEGRATION="1"
py -m pytest -m integration
Remove-Item Env:\OPENMENU_RUN_INTEGRATION
```

## Build and smoke test

```powershell
.\scripts\test_release.ps1 -Version 0.2.0-beta.1
```

The script validates:

- unit tests;
- portable ZIP creation;
- required ZIP files;
- absence of `Run-Portable.cmd`;
- executable startup;
- portable `data/` folder creation;
- SHA256 file generation.

## Manual checks

- Download the ZIP from GitHub Releases, not from local `dist/`.
- Extract it into a new folder.
- Run `OpenMenuGDEMUManager.exe`.
- Confirm Windows warning text is acceptable for an unsigned beta.
- Confirm the setup wizard renders correctly.
- Confirm online sources show OpenMenu Cover API enabled.
- Confirm a cover search works.
- Confirm a clean SD or clean folder can be prepared with an OpenMenu base template.
- Confirm an existing OpenMenu SD scans and shows covers already stored in the SD DAT files.
- Confirm save with only cover changes rebuilds OpenMenu and the SD still boots.
- Confirm save with add/remove game changes compacts slots and the SD still boots.
- Confirm removed games are moved to `_openmenu_gdemu_manager/trash/`.
- Confirm `_openmenu_gdemu_manager/transactions.jsonl` records the operation.
- Confirm Product ID repair prompts do not appear after a clean add/remove/rescan cycle.
- Confirm no personal paths, credentials or private data appear in screenshots.

## Hardware checks

- Boot OpenMenu on Dreamcast/GDEMU after a rebuild.
- Confirm the game list appears with expected titles.
- Confirm covers appear for changed games.
- Launch at least one existing game and one newly added game.
- For large operations, rescan the SD on PC after the console test and confirm no coherence warning remains.

## GitHub release

- Tag format: `vX.Y.Z` or `vX.Y.Z-beta.N`.
- Attach the portable ZIP.
- Attach the `.sha256.txt` file.
- Mark beta builds as prerelease.
- Mention that the build is unsigned.
- Mention that users should make a full SD backup before large operations.
- Mention that the app does not include games, BIOS, commercial game data or SD images.
- Mention that the bundled GPL OpenMenu base assets are used only to prepare folder `01`.

## After release

- Download and test the uploaded asset.
- Update screenshots or docs if the UI changed.
- For public repositories, confirm `main` branch protection is enabled.
