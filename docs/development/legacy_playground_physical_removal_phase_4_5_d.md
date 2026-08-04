# Legacy Playground Physical Removal — Phase 4.5-D

## Status

VALIDATION COMPLETE

## Summary

Phase 4.5-D physically removed the legacy Playground UI implementation,
`playground/frontend`, now that all migration and decision blockers recorded
in [legacy_feature_migration_decision.md](legacy_feature_migration_decision.md)
were resolved through Phase 4.5-C2-E.

## Removal Boundary

Deleted:

```text
playground/frontend
```

Retained:

```text
playground/backend
frontend
apps/reasonscript-ide/ui
```

`playground/frontend` was the legacy Playground UI and is not to be confused
with `frontend` (the Python language frontend / compiler / parser / AST
package) or `apps/reasonscript-ide/ui` (the official IDE UI).

## Changes Made

- Removed `playground/frontend` from the repository.
- Removed `cmd_playground()` and `cmd_frontend()` from `scripts/dev.py`.
- Removed the `test playground-frontend` target from `scripts/dev.py`.
- Removed the legacy frontend build step from `scripts/dev.py`'s `build`
  command.
- Replaced the legacy frontend `npm install` step in `cmd_setup()` with an
  official IDE UI `npm install` step.
- `scripts/dev.py playground` and `scripts/dev.py frontend` now fail with an
  explicit message pointing to `ide` / `ide-ui`.
- Updated `scripts/check_environment.py`'s `REQUIRED_PATHS` to check
  `apps/reasonscript-ide/ui` instead of `playground/frontend`.
- Updated `scripts/test_platform.py`'s `NPM_PROJECTS` to drop
  `playground/frontend`.
- Updated `docs/development/commands.md` and
  `docs/development/test_matrix.md` to remove active legacy frontend
  instructions and build targets.
- Updated `docs/development/legacy_feature_migration_decision.md` and
  `docs/development/legacy_feature_official_ide_placement.md` deletion gate
  status.
- Updated `docs/development/legacy_api_retention_policy.md` and
  `docs/development/editor_state_contract.md` to drop the stale
  `playground/frontend` reference.
- Updated `docs/specs/reasonscript_language_layer_v0_6_d.md`'s frontend
  validation instruction to target `apps/reasonscript-ide/ui`.
- Added `tests/ide/test_phase4_5_d_legacy_playground_physical_removal.py`.

## Deletion Gate

Before Phase 4.5-D:

```text
ALL LEGACY FEATURE DECISIONS RESOLVED — READY FOR PHYSICAL REMOVAL PLANNING
```

After deletion, before validation:

```text
LEGACY PLAYGROUND FRONTEND REMOVED — VALIDATION PENDING
```

After validation:

```text
LEGACY PLAYGROUND FRONTEND REMOVED — VALIDATION COMPLETE
```

## Next

- Phase 5 — Workspace Diagnostics & Project Validation
