# V2 external acceptance protocol

Status: **PENDING**, not executed on a clean Windows VM or Dreamcast.
Use the exact archive/hash recorded in V2_PORTABLE_VALIDATION.md. Local automated
and startup evidence does not satisfy either external gate. Keep runtime logs,
paths, inventories and screenshots private; record only sanitized results publicly.

## Clean Windows

1. Use a fresh Windows VM/profile with no Python, developer Qt or project checkout.
   Record OS build, display resolution/scaling and locale. Do not connect a real SD.
2. Verify the archive SHA256 and extract to a writable folder (also test a path
   containing spaces/non-ASCII characters). Run the EXE, not a source interpreter.
3. Check first-run language, no unsolicited destination selection, icons, error
   reporting, and both languages. Restart and check retained preferences.
4. Run `OpenMenuGDEMUManager.exe --self-test report.json` in that folder. Record
   exit code and report. Require the expected version, startup/icons true,
   errors empty, and sd_scanned/network_requested false. This is startup evidence
   only; it does not validate imports, providers or storage writes.
5. Manually check setup/collection/detail/import/review/recovery screens at
   100%, 125%, 150% and the intended display scaling. Check all six cover cells,
   pagination, fit/enlarge/compare, keyboard focus and reachable fixed footers.
6. Use a disposable local folder and authorized test images: install the base,
   import complete GDI/CDI, rename, choose covers, review/apply and rescan.
   Check that rejected sources leave old contents intact. Check backup and a
   recoverable interrupted operation on that folder only.
7. Test provider search/download with network available, then a controlled
   network failure. Private providers require user credentials; never publish them.
8. Record each case as PASS/FAIL/PENDING with evidence. Preserve failure logs.
   A DLL/startup error fails this gate even when the development-PC check passed.

## Physical SD and Dreamcast/GDEMU

Follow VALIDATION_GAME_LAUNCH.md and RELEASE_CHECKLIST.md. Start only with a
user-approved backed-up disposable SD and verified game sources. Record image
hashes, console/GDEMU version and relevant existing GDEMU.ini settings privately.
Do not overwrite timings or configuration on assumptions.

Exercise setup, existing game scan, new GDI and CDI import, name/cover-only save,
remove/compact, recovery and a PC rescan. Boot the menu and launch an existing
and a newly added game to a playable screen. Check names/covers on console.
Record each result separately: menu boot alone is not game-launch validation.
Unsupported CDI profiles and payload corruption remain outside a passing
supported-descriptor check; obtain a verified source rather than overriding it.

Hardware is currently deferred because no suitable backed-up SD is available.
The automated tests use generated images and have not written to physical media.
