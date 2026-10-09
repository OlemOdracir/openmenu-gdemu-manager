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
the interrupted rollback reproductions. This approval preceded the metadata-only
version bump to `2.0.0.dev2`. The generated
[validation evidence](V2_VALIDATION.md) records the current full harness results.
The dev2 portable was rebuilt and smoke-tested successfully through native Qt;
its evidence is separate in [portable validation](V2_PORTABLE_VALIDATION.md).

## Checks requiring other evidence

- Clean Windows environment and real enabled-provider searches.
- CDI internal descriptor/track-bound validation and unusual GDI layouts.
- Runtime presence/semantic diagnosis of GDEMU.ini: preservation is implemented,
  but the configuration audit required by the launch protocol remains pending.
- Backed-up disposable SD and actual Dreamcast/GDEMU game launch checks, following
  [the launch protocol](VALIDATION_GAME_LAUNCH.md).

Local development approval cannot certify these checks.
