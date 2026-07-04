# Legacy API Retention Policy

## Status

REVIEWED - UPDATED THROUGH PHASE 4.5-C2-E.

This policy records API retention decisions only. It does not remove backend
endpoints and does not change `/api/analyze` or workspace API contracts.

## Summary

The official IDE primarily derives state from `/api/analyze`, while the
legacy Playground UI calls several dedicated endpoints. Phase 4.5-C keeps
the backend stable and records which endpoints are core, which support
migration, and which should become backend-only test or regression workflow
APIs.

Phase 4.5-D physically removed the legacy Playground frontend. This policy
still does not remove backend endpoints, `/api/analyze`, or workspace API
contracts.

## API Decision Matrix

| API | Legacy UI uses | Official IDE uses | Decision | Notes |
|---|---:|---:|---|---|
| `/api/analyze` | Yes | Yes | `KEEP` | Core official IDE analysis API. |
| `/api/core` | No | Yes | `KEEP` | Official IDE core metadata API. |
| `/api/workspace/list` | Yes | Yes | `KEEP` | Workspace API contract. |
| `/api/workspace/read` | Yes | Yes | `KEEP` | Workspace API contract. |
| `/api/workspace/save` | Yes | Yes | `KEEP` | Workspace API contract. |
| `/api/validate` | Yes | No | `KEEP_UNTIL_MIGRATION_DECISION` | May be replaced by analyze-derived validation. |
| `/api/run-all` | Yes | No | `BACKEND_ONLY` | Regression/test platform workflow. |
| `/api/pipeline` | Yes | No | `MIGRATE_OR_REMOVE` | Prefer analyze-derived pipeline data in the official IDE. |
| `/api/export` | Yes | Yes | `KEEP_ARTIFACT_OPERATION_API` | Migrated in Phase 4.5-C2-C without backend contract rewrite. |
| `/api/import` | Yes | Yes | `KEEP_ARTIFACT_OPERATION_API` | Migrated in Phase 4.5-C2-C without backend contract rewrite. |
| `/api/diff` | Yes | Yes | `KEEP_ARTIFACT_OPERATION_API` | Migrated in Phase 4.5-C2-C without backend contract rewrite. |
| `/api/baseline` | Yes | No | `BACKEND_ONLY` | Regression baseline workflow. |
| `/api/language-audit` | Yes | Yes | `KEEP_FOR_OFFICIAL_IDE` | Migrated in Phase 4.5-C2-D without backend contract rewrite. |
| `/api/language-audit/export` | Yes | Yes | `KEEP_FOR_OFFICIAL_IDE_OR_BACKEND_ONLY` | Official IDE can export audit reports while backend/test workflows may also retain it. |
| `/api/examples` | Yes | Yes | `KEEP_FOR_OFFICIAL_IDE` | Migrated in Phase 4.5-C2-E without backend contract rewrite. |

## APIs to Keep

- `/api/analyze`
- `/api/core`
- `/api/workspace/list`
- `/api/workspace/read`
- `/api/workspace/save`
- `/api/validate` until validation migration is explicitly resolved

## APIs to Migrate

- `/api/pipeline`
None. Remaining migration candidates have been resolved or reclassified.

Where possible, migrated official IDE views should consume data already
available through `/api/analyze`. Dedicated endpoints should remain only
when the operation is inherently artifact-oriented, such as export, import,
or diff.

## Artifact Operation APIs

- `/api/export`
- `/api/import`
- `/api/diff`

These endpoints are now used by the official IDE for explicit artifact
operations. They are retained as stable backend contracts and are not
rewritten by Phase 4.5-C2-C.

## Audit Operation APIs

- `/api/language-audit`
- `/api/language-audit/export`

These endpoints are now used by the official IDE for language integration
audit and audit export. They are retained as stable backend contracts and are
not rewritten by Phase 4.5-C2-D.

## Example Operation APIs

- `/api/examples`

This endpoint is now used by the official IDE Sample Browser / Example
Loader. It is retained as a stable backend contract and is not rewritten by
Phase 4.5-C2-E.

## Backend-only APIs

- `/api/run-all`
- `/api/baseline`

These endpoints support regression, baseline, and QA workflows. They may
remain callable by CLI/test infrastructure without a primary official IDE UI
entry point.

## APIs Eligible for Removal

None in Phase 4.5-C. Endpoint removal is out of scope until migrated views,
backend-only workflows, and compatibility notes have been validated.

## Compatibility Notes

- `/api/analyze` remains the preferred official IDE data contract.
- `/api/workspace/*` remains stable.
- Backend endpoints used by legacy-only features must not be removed in this
  phase.
- Any future removal must be paired with a migration record, a compatibility
  note, and a deletion-after-removal validation run.
