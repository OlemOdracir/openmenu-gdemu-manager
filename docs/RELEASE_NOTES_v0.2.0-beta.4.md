# OpenMenu GDEMU Manager v0.2.0-beta.4

Small update focused on version detection.

## Highlights

- The update checker now reads the GitHub releases list and selects the highest available version.
- Beta prereleases are included in update detection, so future beta builds can be offered from inside the app.
- Stable releases with the same base version still sort above beta builds, for example `0.2.0` is newer than `0.2.0-beta.4`.

## Validation

- `uv run pytest`: 176 passed, 2 skipped.
- `.\scripts\test_release.ps1 -Version 0.2.0-beta.4`: portable build and smoke test passed.
- Portable ZIP: `OpenMenuGDEMUManager-0.2.0-beta.4-portable-windows.zip`
- SHA256: `59027AF3502AAB329A1C1DCB9D00EF540769714936B87CFCF727328A72EFBCDB`

## Notes

- This release is intended to make the current public beta line visible to the app update checker.
