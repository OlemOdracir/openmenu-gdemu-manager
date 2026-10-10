# V2 independent audit

Scope: development branch `feature/openmenu-v2`, native application and original
service integration. An independent agent received the repository location and
review scope without the parent conversation or design history. It inspected
code and ran its own tests/reproductions with temporary synthetic discs. No
physical SD, provider traffic, hardware certification or publication was used.

## Initial review

The reviewer withheld approval. Its initial native-Windows run returned
252 passed, 2 skipped and 1 failed. Windows DPR was 2.5; the previous offscreen
checks did not expose the gallery's first-scroll geometry change.

| Finding | Correction and regression |
| --- | --- |
| P1: cancelled review materialized a hidden cover selection | Validate/review drafts first; only materialize after acceptance. Cancel → discard/keep → unrelated save tests ensure the discarded cover is excluded. |
| P1: recovery published an integrity-rejected staging copy | Validate source and existing/new staging during completion, including a service reconstructed without injection. Damaged recovery remains pending and can be reverted. |
| P1: a failed transaction did not prevent another write | Worker and transaction service check pending transactions before any mutation/log. V2 revokes write permission after a transaction failure. |
| P1: late failure lost addition ownership for rollback | Record each publication and retain `created_slots` in failed/recovery states; test failure after publication and safe removal on reversal. |
| P2: bulk-materialized covers survived global discard | Capture game/local-state snapshots before bulk results are adopted; test save failure followed by discard. |
| P2: import feedback contained unformatted placeholders | Format detected count and selected count with the catalog's actual arguments; check final English and Spanish text. |
| P2: import could accept while source inspection ran | Keep selection/prepare disabled until thread cleanup; guard acceptance and register the job with the parent window. |
| P2: native first-scroll layout changed after ensuring visibility | Resolve polished card size hints before scroll placement; exercise the gallery through native Windows at system DPI in the harness. |

Recovery reversal also evacuates published moves before restoring originals,
so cyclic reordering can be reversed without silently leaving swapped slots.
The second review caught two defects in the first correction: removal of an
addition could run twice and erase a restored original; an interrupted reversal
could lose progress and later mark an incomplete operation completed. Both gained
regression fixtures. Reversal now records each removal/evacuation/restoration,
can resume after an interrupted rename, and disables forward completion once
reversal begins. Invalid/insufficient metadata offers manual recovery only.

The gallery correction also required synchronous column reflow and resolved
grid geometry, rather than merely increasing the minimum card height. The
tests now check actual button coordinates and non-overlapping card rectangles.

## Review status

After iterative corrections, the independent reviewer gave **approval for the
current local development code**, with no remaining reproducible blockers from
this audit. Its final independent full-suite run used native Windows at DPR 2.5:
**276 passed, 2 skipped**, including the formerly failing 900×620 gallery and
the interrupted rollback reproductions. Following that approval, the version was
bumped to `2.0.0.dev2`, the reversal message was placed inside both language
catalogs' `strings`, and the geometry assertions were strengthened. Final closure
also caught the root compatibility shim's obsolete version; both root and src
packages now import one shared metadata module, with fresh-interpreter import
and `python -m` startup regression tests.
The reviewer independently ran those two new tests successfully and maintained
its code approval after inspecting the shared metadata and expanded digest.
The generated [validation evidence](V2_VALIDATION.md) records the current full harness results.
The dev2 portable was rebuilt and smoke-tested successfully through native Qt;
its evidence is separate in [portable validation](V2_PORTABLE_VALIDATION.md).

Final artifact closure: the reviewer explicitly approved **delivery of dev2 for
local development**, confirming the final 278 passed / 2 skipped evidence and
27 UI-flow passes per scale/backend. It checked the final ZIP's SHA256, CRC
integrity, executable identity against dist, startup report and documentation
digest. No reproducible blocker remained. This records the historical dev2
artifact approval; the portable validation document identifies the current
development package.

## Checks requiring other evidence

- Clean Windows environment and private/credentialed provider searches. Public
  provider checks were completed in the dev4 follow-up below.
- Real-world unsupported CDI layouts, deeper payload/filesystem checks and
  unusual GDI layouts. Supported CDI descriptor/track-bound validation was
  completed in the dev5 follow-up below.
- Firmware interpretation and game launch on real hardware. Read-only root
  GDEMU.ini diagnosis was completed in the dev4 follow-up below.
- Backed-up disposable SD and actual Dreamcast/GDEMU game launch checks, following
  [the launch protocol](VALIDATION_GAME_LAUNCH.md).

Local development approval cannot certify these checks.

## Dialog design follow-up — 2026-10-09

Dev2 retained the original SD wizard without visual integration. Its functional
approval was communicated too broadly; a callable-method check did not establish
screen coverage. Dev3 adds an explicit retained/replaced inventory and generated
rendering/geometry checks. Scope and corrections are in
[dialog design coverage](V2_DIALOG_DESIGN_AUDIT.md).

A new independent agent received the repository and documented design contract,
without conversation history. It inspected and rendered all retained dialogs,
including first-run language and standard Qt prompts. Approval was withheld for
active-backup closure, untranslated standard buttons, clipped provider controls,
missing metric icons and unsafe setup destination handoff. Corrections were
reproduced through native Windows at system DPR 2.5, including actual diagnostic
and backup workers using generated files, backup failure/retry, pending-work
cancellation and original-UI fallback in a fresh process.

Final explicit independent approval: **current corrected local V2 code and
dialog design scope**, with **63 native tests passed** (workflows, retained
dialogs and provider field localization). No reproducible blocker remained in
that scope. This supplements the dev2 transaction audit; it does not replace
the still-pending clean-Windows, network, physical-SD or Dreamcast gates.

At the earlier checkpoint, the automatic approval reviewer could not run the
packaging verification because the workspace was out of credits. After the
local worktree migration on 2026-10-09, execution resumed: dev3 native packaged
and source startup passed, ZIP CRC passed and the executable identity and
archive SHA256 were checked. See the updated portable validation document.
These local checks do not extend the independent approval to hardware or a
clean Windows VM. Uncommitted changes were preserved during the migration.

## Configuration and collection follow-up — 2026-10-09

Dev4 adds bounded, read-only root GDEMU.ini diagnosis, separate from image
integrity and storage permissions. An independent agent received repository paths
and the documented contract without conversation history. It withheld approval
for stale destination context, excessive RichText rendering, inaccessible
configuration details and an untranslated close button. These were corrected and
reproduced using native Qt at system DPR 2.5. Large-input presentation now bounds
rows and reports omitted counts; the underlying file is preserved completely.

The reviewer checked five configuration states in both languages, 14 hostile or
boundary cases, actual collection-button access and closure, and window geometry.
It explicitly approved the corrected local configuration/UI scope after repeating
15 affected tests. A subsequent visual review found incorrect guidance for an
installed but empty collection. The reviewer rendered empty/unknown/read-only/
missing-cover states in EN/ES, checked top-aligned configuration details, passed
8 focused tests and maintained approval. No additional reproducible blocker
remained in this scope.

The initial configuration/UI review did not certify packaging, clean Windows,
physical SD, Dreamcast, or private providers. The complete final regression results are in
[V2_VALIDATION.md](V2_VALIDATION.md), local package startup evidence in
[V2_PORTABLE_VALIDATION.md](V2_PORTABLE_VALIDATION.md), and the separately executed
public-provider search/download/decoding checks in
[V2_PROVIDER_VALIDATION.md](V2_PROVIDER_VALIDATION.md). Symlink creation is skipped
on this Windows account; containment is reviewed and the test runs on hosts that
permit link creation. Hardware validation is deferred at the user's request;
local tests use isolated destinations and do not discover physical storage.

Final dev4 delivery closure: the independent reviewer explicitly approved
**dev4 for local development**, including packaging and local evidence. It
verified the ZIP/sidecar SHA256, CRC of all 474 entries, archived/built executable
identity, equal source/portable startup reports and current documentation digest.
The final harness recorded **355 passed / 6 skipped**, with **74 UI-flow passes**
for each offscreen 1.25, offscreen 1.5 and native Windows system-DPR run. No
reproducible blocker remained within this scope. This approval does not certify
clean Windows, physical SD/Dreamcast, deep CDI validation or private providers.

## CDI and read-only agent queries - 2026-10-09

Dev5 adds an original bounded CDI structural parser and headless Python/JSON
queries. A separate reviewer, without conversation history, checked current
source, synthetic fixtures, primary format references, original transaction
integration, query side effects and six native EN/ES import states. Initial
approval was withheld for stale UI scope text, inconsistent CLI error envelopes,
GDI access failures reported as corruption, untranslated diagnostic fields,
historical signed-index interpretation and a clipped format heading.

All six findings were corrected and independently reproduced. The reviewer ran
111 focused tests, checked both CLI failure envelopes, exercised an actual
GDI read denial, inspected EN/ES reason codes, and visually reviewed six native
screenshots. High-bit indices now require review rather than an unsupported
corruption claim. No remaining concrete defect was found in this scope. The
reviewer explicitly approved the CDI parser, read-only queries/CLI and their
presentation; delivery closure still requires final generated regression and
portable startup evidence.

This review does not certify payload checksums/filesystem integrity, every
real-world CDI layout, firmware support, clean Windows, physical SD or Dreamcast
launch. MCP remains a documented proposal: there is no MCP server/SDK integration
or initialize/tools/list/tools/call evidence. Queries do not enumerate drives,
start GUI/migrations or perform writes. The CLI requires an explicit destination.

The final mandatory harness passed 422 tests / 6 skips, followed by 80 UI-flow
passes each at offscreen 1.25, offscreen 1.5 and native Windows system DPR 2.5.
The freshness check confirms its generated source digest. Source and portable
startup report dev5 with icons/startup true and no errors. The independent
package review confirmed ZIP/sidecar hash, CRC of 474 entries, archived/built
EXE identity, and embedded CDI/storage/UI bytecode plus EN/ES JSON correspondence
with the final source. There is no separate CLI or MCP transport in the GUI
portable; the source CLI was also exercised through its installed entry point.

Final explicit independent disposition: **dev5 approved for local development
and delivery**, with no reproducible blocker in the audited scope. The reviewer
independently checked generated XML counts/digest, archive correspondence and a
fresh installed-CLI call on a synthetic CDI without runtime/document migration.
This closes the local integration conditions, not the remaining release gates.
