# Release checklist

## Before building

- Confirm the repository is clean: `git status --short`.
- Confirm no credentials, ROMs, BIOS files, SD backups, logs or cache files are staged.
- Run unit tests: `py -m pytest`.
- Run public API integration tests when the API changed:

```powershell
$env:OPENMENU_RUN_INTEGRATION="1"
py -m pytest -m integration
Remove-Item Env:\OPENMENU_RUN_INTEGRATION
```

## Build and smoke test

```powershell
.\scripts\test_release.ps1 -Version 0.1.0-beta.1
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
- Confirm no personal paths, credentials or private data appear in screenshots.

## GitHub release

- Tag format: `vX.Y.Z` or `vX.Y.Z-beta.N`.
- Attach the portable ZIP.
- Attach the `.sha256.txt` file.
- Mark beta builds as prerelease.
- Mention that the build is unsigned.

## After release

- Download and test the uploaded asset.
- Update screenshots or docs if the UI changed.
- For public repositories, confirm `main` branch protection is enabled.
