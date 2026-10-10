# Game integrity and launch validation

This protocol applies whenever a correction affects library scanning/import,
storage diagnostics, setup, copying, slot transactions, or OpenMenu rebuilding.
It supplements `AGENTS.md` and the release checklist. Documentation of this
protocol does not itself implement the runtime checks described below.

## Regression to prevent

OpenMenu can display its list and covers while every selected game returns to
the Dreamcast BIOS. In the investigated case, the game folders lacked tracks
declared by their GDI descriptors. The source library was incomplete too, and
the Manager reported successful copies because it compared only total bytes.
The target SD also lacked `GDEMU.ini`, which the working backup contained.
Missing configuration was an additional finding, not a proven cause of that
launch failure. FAT32 and a bootable menu did not prove game integrity.

## Automated acceptance checks

Use synthetic fixtures; do not commit ROMs, BIOS, real game data, private paths,
library scans, SD backups, or hardware logs.

| Case | Required evidence |
| --- | --- |
| GDI with one referenced track missing | Reject with the descriptor and missing filename; no successful save or SD mutation. |
| Descriptor present but all its tracks missing | Reject even though copying the folder would preserve its total byte count. |
| Empty track or a file ending mid-sector | Reject with a specific reason. Honor declared offsets when checking sector alignment. |
| Truncation at a whole-sector boundary | Detect when track bounds, a known matching reference, or supported filesystem extents prove required data is absent; sector divisibility alone is insufficient. |
| Valid GDI with spaces/quoted track filenames | Accept and copy all referenced tracks with path containment enforced. |
| Supported valid CDI | Validate its descriptor and track bounds within the file; accept without external GDI tracks. Unsupported variants must be reported distinctly from confirmed corruption. |
| File lost or damaged during staging | Validate the destination before publishing the slot; do not rely only on aggregate byte totals. Preserve recovery metadata and the previous menu. |
| Source rejected in a transaction that also removes/reorders games | Reject before moving/deleting existing slots or replacing menu `01`. |
| Copy failure | Record failure, preserve the source, and leave recovery or rollback possible. |
| Missing `GDEMU.ini` | Surface a configuration finding independently of image integrity; absence must not be described as proof of corruption or hardware failure. |
| Existing `GDEMU.ini` | Preserve its bytes/settings unless the user authorized a configuration change. |
| Invalid configuration values | Identify invalid supported keys/values using documented constraints; do not guess replacement values. |

Basic validation must happen before any target SD mutation. After staging,
validate the actual destination image again before publishing it and marking
the operation successful. Path/volume diagnostics and `write_allowed` remain
required; this protocol does not replace those protections.

For deeper audits, record full-read errors, SHA256 references, and EDC checks
where the stored sector format retains EDC. Audio and 2048-byte data tracks
lack that stored check in these formats. A fresh SHA256 is a baseline, not proof
of correctness without a trusted matching reference. Modified images may have
omitted or stale checksums. Files intended as dummy padding and unusual image
layouts must be reviewed before declaring a filesystem anomaly unusable.
Report limitations explicitly; do not label every suspicious image corrupt.

## Configuration checks

- Inspect `GDEMU.ini` in the SD root, independently of the menu image.
- Record whether it exists and the relevant timing/reset/image-check settings.
- When diagnosing a regression, compare with a known working card or backup.
- Do not automatically copy another card's settings, disable image checks, or
  use fixed clone/original timings without hardware evidence and authorization.
- If changing configuration, preserve a backup and test one change at a time.

GDEMU documents its configuration keys and ranges here:
https://gdemu.wordpress.com/operation/gdemu-operation/

## Physical launch check

After authorized, backed-up writes and successful automated checks:

1. Use a structurally verified complete game image; do not reuse an incomplete
   library image as a test of the menu or console.
2. Record the build, console/GDEMU variant if known, SD filesystem, configuration,
   image format, region/disc identity, and relevant image/reference hashes.
3. Cold-boot OpenMenu and check list and covers.
4. Launch at least one existing verified game and one newly added verified game.
   Confirm the game reaches a playable screen instead of returning to the BIOS.
5. Rescan on PC after the console test and verify image/slot/menu consistency.
6. Report automated validation and hardware results separately. If there is no
   console access, mark physical launch validation pending. Do not claim that
   an image works merely because files and checksums pass.

Keep private evidence outside the public repository. Never write to a physical
SD merely to satisfy a checklist without user authorization and the project's
storage diagnostics, backups, and recoverable transaction requirements.
