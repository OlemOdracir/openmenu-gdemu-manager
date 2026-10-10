## Summary

Describe the change and why it is needed.

## Tests

- [ ] `py -m pytest`
- [ ] Integration tests, if API behavior changed
- [ ] Manual test, if UI or SD write behavior changed
- [ ] `docs/VALIDATION_GAME_LAUNCH.md` covered for import/storage/copy/setup/slot/menu changes: reject incomplete sources before SD mutations, validate staged images, and preserve/report `GDEMU.ini`
- [ ] Physical launch with verified complete existing/new images passed, or explicitly reported pending

## Safety

- [ ] No ROMs, BIOS files, copyrighted content, SD backups, logs, cache files or credentials are included.
- [ ] SD write behavior was reviewed if this PR changes file operations.
- [ ] Documentation was updated if user-visible behavior changed.
