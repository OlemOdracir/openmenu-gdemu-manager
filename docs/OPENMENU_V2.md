# OpenMenu GDEMU Manager v2

Version `2.0.0.dev5`, development branch `feature/openmenu-v2` based on `develop`.
This is a real PySide6 application over the original services. It is not the
HTML mockup or a simulation, and is not yet a hardware-validated public release.

## Purpose and design

The collection answers which games are present and which need a cover. It uses
compact rows, small uncropped thumbnails, disc ID, region and pending states.
The cover workspace helps fans find a design, inspect its scan and choose it.
It starts with six alternatives per page, across every available region. Click
an image to enlarge it; compare two distinct images side by side or by alternation,
with zoom and synchronized pan. The OpenMenu preview uses the project's actual
Pillow normalizer. The original scan is not color-corrected or cropped.

Shared tokens, action semantics, Tabler SVG icons and Qt atoms live in
`ui/v2/design.py` and `resources/v2/`. Bitmap assets remain covers and branding.
There is no Tailwind/browser dependency. The original template registry still
supports palettes, backgrounds and music. V2 gives the default formal template
the approved warm orange palette; explicitly selected external/arcade palettes
are translated to the same semantic tokens. Templates cannot change action semantics.

SD preparation now uses `ui/v2/setup.py`: compact destination selection, a clear
status and next action, technical diagnostics on demand, and an explicit
installation success state before entering the collection. Invalid edits revoke
the old destination approval. An unrelated working directory is not presented
as the user's SD at first run. Original diagnosis, installation and backup
services remain authoritative. `retained_dialogs.py` registers backup, upgrade,
review, providers/credentials, language, About and bulk progress presentation;
standard messages and template inputs share command icons and translated labels.
Native file pickers remain OS-owned. See [screen coverage and visual review](V2_DIALOG_DESIGN_AUDIT.md).

## Original functionality retained

| Function | V2 integration |
| --- | --- |
| SD / backup folder diagnosis, FAT32 and write permission | Original diagnostic worker and safeguards; destination summary and reason visible. |
| Empty SD setup, menu installation and old-menu upgrade | Compact V2 setup and adapted original upgrade, preserving backup decisions and OpenMenu assets. |
| Read games, names, IDs, regions and menu inconsistencies | Original scanner/models; compact table and full game information dialog. |
| GDI/CDI file or recursive folder import | Real source inspection in a worker; explicit selection, global Todos, duplicates initially unchecked, invalid GDI/CDI blocked with reason; unsupported CDI profiles distinguished. |
| Add, remove, compact slots, write names and rebuild 01 | Original workers/slot transactions/rebuilder; changes remain pending until confirmed. |
| Search providers, matching thresholds and caching | Original search services/settings; remote image preparation stays outside the UI thread. |
| Automatic bulk proposals and batch approval | Original bulk workers/quality rules; proposals do not automatically become a manual Save. Explicit batch Save retains the original review/confirmation. |
| Current cover, quality, dimensions, source and previous covers | Game/image information and persistent original cover library. Full metadata remains on GameItem. |
| Import local covers and web search templates | Original file picker/providers and configured web templates, disc-ID search, source opening, originals folder. |
| Backup, transaction recovery and internal trash | Original services and dialogs, never replaced by mockup code. |
| Spanish/English, language packages | Original language registry; V2 strings/actions use its catalogs. |
| Install templates, backgrounds and music | Original template registry/menu/audio controller. |
| JSON/TSV export, logs and updates | Original menus/services. The displayed version comes from the current code. |

## State and interaction contract

1. Selecting a destination diagnoses it before any write. A folder that cannot
   be written remains inspectable when the original diagnostic allows scanning.
2. Source import is separate from SD contents. Preparing games adds pending
   rows; it does not copy files. Invalid sources show a reason. Supported CDI
   descriptors and declared track bounds are checked; unknown layouts require
   review. No structural check guarantees payload integrity or game boot.
3. Entering bulk mode checks only games without covers. Todos affects the entire
   collection, independent of filters. Clicking a row or its checkbox toggles
   once. Search selected keeps the mode; individual search/info/remove, import,
   scan, destination, save and other menu actions leave it first.
4. The search text is temporary. Only Guardar nombre adopts it for OpenMenu.
   IDs, internal name, disc, VGA, version/date and aliases remain unchanged.
5. Choosing a cover creates a draft. Searching, inspecting, comparing and opening
   the web do not choose it or write to the SD. Keeping the current image does
   not prepare a replacement. Exact image duplicates are merged; different
   scans/tones remain alternatives under the original deduplication rules.
6. Review and save validates the intentional choices and confirms the storage
   plan before materializing them through the original cover service and
   starting the transactional worker. Cancelling leaves drafts and local cover
   state untouched; Discard/Keep can remove the choice without a hidden save.
   Successful save rescans
   after its thread finishes. Unchosen bulk proposals are excluded from manual Save.
7. Closing/changing destination/rescanning asks before abandoning pending work.
   Discard restores local edited state and clears session changes; archived
   original-cover history is preserved. An active storage job prevents closing.
   Search completion after closing its dialog is ignored; its thread stays alive
   until cleanup so Qt cannot destroy a running worker.

## Source integrity added in v2

The v1 baseline has byte-total copy verification. V2 additionally validates GDI
track count/order, quoted filenames, path containment, offsets, missing/empty
tracks, incomplete sectors and provable ISO9660 volume truncation before an
addition can mutate the SD. It validates the staged destination again before
publishing a slot. A failed copy remains recoverable through original transaction
metadata. Existing GDEMU.ini is preserved. The runtime diagnosis separately reports its
optional absence, unreadable content, unsupported sections/keys, duplicate known
keys and invalid documented values. Root settings and line numbers appear in
expandable technical details with allowed ranges. No timings or other values
are inferred, repaired or written, and configuration findings do not certify
image integrity or change storage permissions. The view bounds the number of
rendered rows and reports omitted counts; the original file remains complete.
Recovery revalidates source and staging, records ownership of published additions
and retains it after late failures. Pending transactions block new writes from
both the worker and service until completed/reverted. Reversal evacuates owned
published moves before restoring originals, including slot reorder cycles.

These checks are structural. Supported CDI footer/track layouts now receive
bounded descriptor and extent validation before import, before any addition
mutates storage, after staging and during recovery. Unsupported layouts are
reported for review separately from confirmed structural failures. Deeper disc
checksum/filesystem-extents audits remain separate work; a structurally checked
CDI is not certified intact or bootable. See [CDI contract](CDI_VALIDATION.md). A GDI with
no supported filesystem size evidence can still be truncated on a whole sector
boundary without this validator proving it. Bootability requires hardware evidence.
See [launch protocol](VALIDATION_GAME_LAUNCH.md).

## Run, validate and package

```powershell
python -m pip install -e ".[dev,build]"
python -m openmenu_gdemu_manager
python -m openmenu_gdemu_manager --legacy-ui
python scripts/validate_v2.py
python scripts/validate_v2.py --check-docs
./scripts/build_portable.ps1 -Version "2.0.0-dev5"
./dist/OpenMenuGDEMUManager-Portable/OpenMenuGDEMUManager.exe --self-test report.json
```

The harness regenerates [validation evidence](V2_VALIDATION.md). Re-run it after
V2 code/resource/test changes; `--check-docs` rejects stale source evidence.
On Windows it also tests UI flows with the native Qt backend at the system DPI,
because offscreen measurements alone can miss native layout changes.
See the [independent audit and corrections](V2_INDEPENDENT_AUDIT.md).
The self-test verifies native startup and packaged icons without SD/network work.
Generated artifacts, caches, ROMs, real library inventories and mockup sample
covers must not be committed. No new third-party dependency was introduced.

Keep this work on the feature branch until review, then merge to develop. Main
receives only a validated release. Every commit uses Conventional Commits and
the repository's existing commit-msg/pre-push hooks.

## Remaining release checks

- Portable launch in a clean Windows VM, beyond this development PC; use
  [the acceptance protocol](V2_EXTERNAL_ACCEPTANCE.md).
- Private/credentialed provider checks as configured by the user. Public OpenMenu,
  Libretro and Cover API search/download/decoding passed the opt-in tests; see
  [provider evidence](V2_PROVIDER_VALIDATION.md). Offline suites still skip network calls.
- Real-world CDI variants outside the supported structural profiles, deeper
  checksums/filesystem extents and unusual GDI layouts.
- A disposable backed-up SD and Dreamcast/GDEMU test: setup, add GDI/CDI, rename,
  change covers, remove/compact, then actually launch each game.

The original v1 remains available through `--legacy-ui`. Its existing checkout
and portable installation are not replaced by creating this branch/build.

## Agent access

A read-only headless CLI now shares validation/diagnostic services with the
application. `python -m openmenu_gdemu_manager.cli --language es validate-image
"path/to/disc.cdi"` returns schema-versioned JSON and a categorized exit code.
`diagnose-storage "path/to/destination"` requires an explicit path and performs no
automatic drive discovery. It does not authorize or execute writes.
[MCP evaluation](MCP_EVALUACION.md) recommends an optional local stdio adapter
using the official SDK. No MCP server or remote API is activated in this phase.
The source installation provides the CLI entry point; the GUI portable does not
include a separate console executable.
