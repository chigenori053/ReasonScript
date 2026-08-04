# ReasonScript IDE Phase 4.5-A - IDE Implementation Dependency CodeReview - 2026-07-04

## Status

REVIEWED

Deletion Gate: NOT MET

Next Phase: Phase 4.5-B — Official IDE Command Wiring

## Summary

Phase 4.5-A executed the CodeReview process required before consolidating
ReasonScript IDE implementations and physically removing the legacy
Playground frontend.

The review investigated `apps/reasonscript-ide/ui`, `playground/frontend`,
and `frontend`, classified their roles, mapped command/test/documentation/API
dependencies, and determined which legacy UI functionality must be migrated
or deprecated before deletion.

## Findings

- `apps/reasonscript-ide/ui` classified as `OFFICIAL_IDE_UI`. Confirmed React
  + TypeScript + Vite + Tauri stack with 15 views and browser/desktop
  `PlatformAdapter` implementations. **Not wired into `scripts/dev.py`** —
  only referenced by `scripts/test_platform.py`.
- `playground/frontend` classified as `LEGACY_IDE_UI`. Confirmed React/JSX +
  Vite stack, 30 components, and 14 dedicated `/api/*` endpoint calls. It is
  the sole frontend `scripts/dev.py` currently launches, builds, or tests.
- `frontend` classified as `LANGUAGE_FRONTEND`, confirmed to be a pure
  Python compiler/parser/AST/LSP/schema package with no `package.json` and
  no relation to IDE UI work. Excluded from this initiative entirely.
- 16 of 32 tracked Playground features have no counterpart in the official
  IDE UI; 4 of those (Run all, Baseline, Regression runner, Sample selector)
  look like CI/QA/dev tooling and require an explicit product decision
  rather than automatic migration.
- Deletion Gate (Section 10 of the governing spec) checked against current
  repository state: **0 of 7 conditions met.**

## Added

- Added `docs/development/ide_code_review_phase_4_5_a.md` — full CodeReview
  report (directory inventory, command/test/API/feature-parity matrices,
  documentation impact, deletion impact, required migrations, safe deletion
  conditions, final recommendation).
- Added `docs/development/ide_version_inventory.md` — detailed
  per-directory inventory backing the CodeReview report.
- Added `docs/development/legacy_playground_removal_impact.md` — deletion
  impact analysis: scripts, tests, and docs that break on deletion today,
  and the authoritative deletion-gate checklist.
- Added this changelog entry.

## Policy

- `apps/reasonscript-ide/ui` is confirmed as the candidate official IDE UI.
- `playground/frontend` is confirmed as the candidate legacy UI for future
  physical removal, pending Phase 4.5-B.
- `frontend` is confirmed as the language/compiler frontend and is excluded
  from this initiative.
- `playground/backend` is explicitly retained.
- Physical deletion remains prohibited until the deletion gate checklist in
  `legacy_playground_removal_impact.md` is fully met.

## Non-Goals

- No deletion performed or scheduled in this phase.
- No parser/runtime/IR changes.
- No backend API contract changes.
- No Phase 5 implementation.

## Next Phase

Phase 4.5-B — Official IDE Command Wiring: wire `apps/reasonscript-ide/ui`
into `scripts/dev.py` (`setup`, `build`, `test smoke`, and a new/renamed
`ide`/`ide-ui`/`test ide-ui` command), obtain product decisions on the 4
CI/QA-flavored features, and migrate or deprecate the remaining 12
MIGRATE_REQUIRED features before Phase 4.5-C (physical deletion) can be
scheduled.
