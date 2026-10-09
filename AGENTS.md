# AGENTS Contract (Public)

## V2 integration evidence

For V2 code, resource or regression-test changes, run `python scripts/validate_v2.py`
before committing. It regenerates `docs/V2_VALIDATION.md`; do not manually edit
its results. `python scripts/validate_v2.py --check-docs` checks that its source
digest is current. Update `docs/OPENMENU_V2.md` when a flow or retained feature
changes. Keep the original services/transactions and `--legacy-ui` fallback.
Do not replace real services with prototype fixtures. Public release still
requires the hardware/clean-Windows gates documented for V2.

This file defines mandatory engineering rules for contributors and AI agents.

## Git workflow

Follow [Basic Gitflow and Conventional Commits](docs/GIT_WORKFLOW.md).

1. Use `develop` for ongoing integration; keep `main` for stable validated versions.
2. Use focused topic branches from `develop` for larger changes and target their PRs to `develop`. Promote validated versions through a PR from `develop` to `main`; synchronize hotfixes back into `develop`.
3. Use Conventional Commit headers for every new commit, including merges, squashes, reverts, releases and bots, and for PR titles. No automatic-message exception. Enable the versioned commit-msg/pre-push hooks, run the policy checks and preserve their CI validation. Do not rewrite public history or move the grandfathered history anchor to hide violations. Report server enforcement limitations accurately; see docs/GIT_WORKFLOW.md.
4. Preserve unrelated staged/unstaged changes. Commit only the files or hunks belonging to the current task.
5. A public branch or draft PR is public. Apply the content/licensing rules in CONTRIBUTING before publishing prototype assets.

## Safety rules for SD writes

1. Never write to an SD path without passing storage diagnostics and `write_allowed`.
2. Never delete game folders directly. Use transaction/staging flows and internal trash.
3. Never use in-place `track05.iso` patching as the main save path.
4. Slot operations must be planned and recoverable (`plan.json`, `state.json`, logs).
5. Validate path containment for all temp/trash/final slot paths before file moves.

## Transaction and recovery rules

1. Write transaction metadata atomically (temp file + replace in same directory).
2. Any incomplete slot transaction blocks normal save until resolved.
3. If transaction metadata is missing/corrupt, only offer limited manual recovery UI.
4. Rollback must not delete slots unless they were created by that same transaction.

## OpenMenu rebuild rules

1. Rebuild menu `01` in staging, never by fixed-block patching.
2. Replace `01` using safe swap (`01.new` -> validate -> replace -> validate).
3. Keep technical backup of `01` before replacement.
4. Add timeout and clear error reporting for `buildgdi` execution.

## Game integrity and launch validation

For changes to library import, game copying, storage diagnostics, setup, slot
transactions, or menu rebuilds, follow `docs/VALIDATION_GAME_LAUNCH.md`.

1. Validate every GDI track reference before any SD mutation and validate the copied image before publishing its slot. Comparing total source/destination bytes alone is insufficient: both can be equally incomplete.
2. Reject missing/empty tracks, invalid descriptors, partial sectors, and demonstrably truncated images with actionable errors. Support quoted filenames and supported CDI layouts; do not impose GDI requirements on CDI images.
3. Cover an incomplete source, a complete source, and a damaged staging copy with synthetic regression fixtures. Rejection must preserve existing slots/menu and transaction recoverability; it must not record a successful save.
4. Inspect root `GDEMU.ini` and report missing or invalid configuration separately from game integrity. Preserve existing settings. Do not silently change timing, `reset_goto`, or `image_tests` based on guesses about hardware.
5. Distinguish confirmed structural failures, checksum anomalies requiring review, and images with no detected failure. A checksum mismatch or a SHA256 without a known reference does not alone establish an unusable game.
6. A menu that boots is not evidence that games launch. Before declaring a launch fix hardware-validated, test an existing and a newly added verified complete image on Dreamcast/GDEMU. If hardware is unavailable, record this check as pending, never passed.

## Dependency and licensing rules

1. Every bundled external tool must have declared license and version/hash evidence.
2. Do not introduce undeclared binary dependencies.
3. Any remote input must use HTTPS, timeout, size limits, and content-type validation.

## UI/i18n rules

1. All user-visible strings must be in i18n keys (`en` and `es`).
2. No hardcoded end-user text in widgets/dialogs.

## Release gate (required)

Before a release:

1. Run automated tests.
2. Build portable package.
3. Test in a clean Windows VM.
4. Validate with a physical SD + Dreamcast smoke test.

## Local/private instructions

Use `AGENTS.local.md` for personal or machine-specific instructions.
That file is intentionally ignored by Git.
