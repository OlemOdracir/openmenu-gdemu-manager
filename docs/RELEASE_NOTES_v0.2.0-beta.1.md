# OpenMenu GDEMU Manager v0.2.0-beta.1

Public beta focused on safe OpenMenu/GDEMU SD management from a portable Windows app.

## Highlights

- Add GDI/CDI games to numbered GDEMU slots.
- Mark games for removal and move them to SD internal trash instead of deleting immediately.
- Compact game folders from `02` upward to avoid empty OpenMenu entries.
- Rebuild OpenMenu folder `01` with `buildgdi.exe` instead of patching a fixed-size block in `track05.iso`.
- Sync cover art into OpenMenu DAT files.
- Read existing covers from SD DAT files on scan.
- Detect Product ID mismatches and repair synthetic `SLOTxxx` menu entries when the disc exposes a real Product ID.
- Show internal disc title when available, useful for multi-disc or duplicate-looking games.
- Spanish and English UI.
- Portable runtime: no Python installation required.

## Safety

- The app does not format SD cards.
- A technical backup of folder `01` is created before replacing OpenMenu.
- Removed games are moved to `_openmenu_gdemu_manager/trash/`.
- Operations are logged in `_openmenu_gdemu_manager/transactions.jsonl`.
- A full SD backup is optional, but recommended before large operations.

## Known limits

- The app is unsigned; Windows SmartScreen may warn on first launch.
- The app does not include games, BIOS, OpenMenu distributions or SD images.
- Direct ScreenScraper usage requires the user's own credentials.
- This is a beta. Keep backups and test changes before relying on one SD as the only copy.

## Validation

- Unit test suite passes.
- Public Cover API integration tests pass when enabled with `OPENMENU_RUN_INTEGRATION=1`.
- Large add/remove/cover rebuild flow has been tested on real Dreamcast/GDEMU hardware.
