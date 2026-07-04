# ReasonScript IDE Phase 4.5-C - Legacy Feature Migration / Deprecation Decision - 2026-07-04

## Status

REVIEWED

## Summary

Phase 4.5-C classifies legacy Playground UI features and APIs before the
legacy frontend can be physically removed.

This phase does not delete `playground/frontend`. It records which features
must be migrated to the official IDE UI, which APIs should remain
backend-only, and which features remain deferred.

## Added

- Added legacy feature migration decision document.
- Added legacy API retention policy.
- Added official IDE placement policy for migrated legacy features.
- Added Phase 4.5-C docs contract tests.

## Decisions

- Classified legacy-only features into `ALREADY_SUPPORTED`,
  `MIGRATE_REQUIRED`, `BACKEND_ONLY`, `DEPRECATE_ALLOWED`, and `DEFERRED`.
- Classified legacy-only APIs into keep, migrate, backend-only, deferred, or
  removal candidate decisions.
- Preserved the Standard IDE Layout.
- Kept physical deletion out of scope.

## Not Changed

- `playground/frontend` is not deleted.
- `playground/backend` remains unchanged.
- Parser, runtime, Reason IR, and API contracts are unchanged.
- Official IDE feature migration is not implemented in this phase.

## Deletion Gate

Decision complete, implementation not complete.
