# V2 dialog design coverage

Development checkpoint: `2.0.0.dev3`. This review closes the missed visual
integration of the original SD wizard. The dev2 audit remains historical
functional/transaction evidence; its approval did not certify all screens.

## Contract and ownership

- V2 tokens define color, typography, spacing, controls and icon size. Commands
  use the shared Tabler outline family. Bitmap covers and brand logos retain
  their purposes; diagnostic and backup illustrations are replaced with outline icons.
- One clear primary next action; a compact state/reason; secondary navigation
  and expandable technical information. Neutral/not-applicable information
  must not be presented as a successful SD check.
- Original services, counts, permissions, backup decisions, cancellation signals,
  recovery options and defaults are retained. Native file pickers remain OS UI.
- Setup is a dedicated view over original services. Other retained dialogs have
  an explicit presentation registry, not a blanket claim that inherited UI is
  approved. The adapter translates roles without reconnecting action signals.

## Screen inventory

| Screen / state | Treatment and verification |
| --- | --- |
| No destination chosen | Compact V2 setup, empty route, Select SD as primary; no startup alarm about the executable directory. |
| Empty compatible destination | Install OpenMenu as primary; confirmation remains required; outcome remains visible until Continue. |
| Ready / read-only / blocked destination | Original diagnostic remains authoritative; use/install hidden when unavailable; choose another destination is primary for a blocked path. |
| Edited destination | Prior approval invalidated; current path diagnosed again before installation/acceptance. |
| Diagnostic details | Expandable scroll area with all diagnostic categories and original path/classification/menu/permission values; local filesystem N/A is plain neutral text. |
| Backup in setup | Original worker/service/registry; route changes and closure blocked through thread cleanup. |
| Backup prompt | Compact hero and outline source/destination icons; choose destination separate from backup/skip/cancel; required backup still omits Skip. Cancel/window close cannot abandon an active worker. |
| Old-menu upgrade | Shared hierarchy/roles/icons; backup-first, update and cancel preserved. |
| Manual and batch save review | All five counts retained: covers, additions, deletion, slot moves and ID corrections; transactional explanation and destination preserved. Shared hierarchy/file icons replace missing-icon warnings. |
| Provider settings | All seven columns retained and scrollable; buttons and priority controls fit cells; current statuses, signup, testing and credentials remain available. |
| Nested provider credentials | Field names localized in English/Spanish; original field identities, ranges, password modes and acceptance values preserved. |
| First-run language | V2 theme/adapter installed before main window construction; brand allowed, Use/Cancel roles and icons. |
| About | Brand, actual shared version and repository/contact/data directory preserved; shared title and Close action. |
| Bulk progress | Consistent cancel icon and label; original cancellation signal/reject behavior preserved. |
| Other busy progress | Token-based panel, spinner colors and content-height calculation instead of fixed clipping height. |
| Recovery / repair / generic confirmation | Standard and authored QMessageBox roles/defaults/conditional branches preserved; icons and translated standard buttons. |
| Template URL / music volume | QInputDialog buttons receive V2 icons and translated labels; OS controls and values preserved. |
| Exports / template ZIP / image and game pickers | OS-owned file dialogs; parent busy/result/error UI uses V2 treatment. |
| Collection / cover details / import | Existing dedicated V2 views retained and still exercised by workflow tests. CandidateDialog, CoverPreviewDialog, AddGameDialog and original SetupWizardDialog are explicitly replaced. |

## Evidence and approval boundaries

`scripts/validate_v2.py` executes dialog coverage alongside production flows at
offscreen scales 1, 1.25, 1.5 and native Windows system DPI. It regenerates
`docs/V2_VALIDATION.md` and saves snapshots in
`build/v2-validation/visual-<backend>-<scale>/`. Coverage includes setup states,
disclosure, install cancel/failure/success, stale paths, all retained classes,
button reachability, provider-cell scrolling, standard labels and original-UI
fallback. A new exported original dialog fails the explicit disposition test.

An independent reviewer, without conversation history, inspected reachable
paths and rendered setup, backup, upgrade, review, providers/credentials,
language, About, progress, messages, template input and busy overlay through
native Windows at DPR 2.5 in English/Spanish. It found active-backup closure,
untranslated Qt buttons, clipped provider priority and missing metric icons.
These received corrections. Its actual backup-worker runs used generated files,
including failure and retry; they did not write to a physical SD.

The same reviewer caught a destination handoff defect: changing the path before
asking to discard pending changes could leave old games approved for the new
destination. Setup now checks abandonment before opening, clears destination-owned
views and revokes old permissions when switching. Diagnostic-driven setup/backup/
recovery dialogs wait for the diagnostic thread to finish. Regression tests cover
declined abandonment, active jobs, accepted switching and deferred handoff.

Visual/behavior approval is scoped to the reviewed local development screens.
It does not certify every external template, pathological screen/window size,
OS-owned file picker appearance, provider network availability or hardware.
Clean Windows, physical SD and Dreamcast gates remain in OPENMENU_V2.md.
Final independent status is recorded in V2_INDEPENDENT_AUDIT.md after closure.
