# AGENTS Contract (Public)

This file defines mandatory engineering rules for contributors and AI agents.

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
