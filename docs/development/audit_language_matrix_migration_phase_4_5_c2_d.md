# Audit / Language Audit Matrix Migration Phase 4.5-C2-D

## Status

IMPLEMENTED for Phase 4.5-C2-D.

## Summary

Phase 4.5-C2-D migrates the legacy Audit and Language audit matrix workflow
into the official IDE without deleting `playground/frontend` and without
rewriting backend API contracts.

Migrated features:

- Audit
- Language audit matrix

## Placement

The migration preserves the Standard Layout top-level tabs:

- Right Inspector: `Overview`, `Plan`, `Simulation`, `Knowledge`, `Artifacts`
- Bottom Tool Window: `Problems`, `Output`, `Logs`, `Tests`

Audit placement:

- `Overview`: audit summary and audit/export actions.
- `Tests`: language audit matrix, category rows, expected/actual status, and
  connected/missing/warning/error counts.
- `Problems`: disconnected rows, missing compiler/runtime/IDE mappings, audit
  compatibility warnings, and audit export failures when structured.
- `Artifacts`: raw audit report, raw matrix JSON, audit metadata, and audit
  export result.
- `Output`: audit started/completed/failed and audit export
  started/completed/failed logs.

## API Policy

The official IDE calls the existing audit endpoints:

- `GET /api/language-audit`
- `POST /api/language-audit/export`

The migration does not remove endpoints and does not change backend request or
response schemas. It is implemented without backend contract rewrite. Client
code tolerates audit failure and malformed optional sections by preserving raw
results and rendering fallback states.

## Audit Export Policy

Audit export uses the existing `/api/language-audit/export` endpoint. Export
result data is displayed in Artifacts, export operation logs are displayed in
Output, and structured export failures are normalized into Problems.

## Audit Freshness Policy

Audit results are tied to the current file or workspace snapshot when the
operation runs. Source changes after audit mark the audit result as stale. A
stale audit result remains visible, but the official IDE reports it as a
warning rather than a failure.

## View Model

`apps/reasonscript-ide/ui/src/viewModels/languageAudit.ts` provides the
normalized audit model:

- `AuditStatus`
- `AuditItemStatus`
- `AuditIssue`
- `AuditOperationLog`
- `LanguageAuditMatrixRow`
- `LanguageAuditSummary`
- `LanguageAuditExportResult`
- `LanguageAuditViewModel`

`buildLanguageAuditViewModel` accepts unknown state, tolerates missing audit
results, preserves raw audit/export results, normalizes matrix rows and
issues, computes deterministic counts, and returns unavailable fallbacks when
no audit has run.

## Deletion Gate Impact

All `MIGRATE_REQUIRED` legacy UI features are now migrated. Physical deletion
of `playground/frontend` is still blocked by the remaining deferred Sample
selector decision and deletion-after-removal validation planning.

Current deletion gate:

ALL REQUIRED MIGRATIONS COMPLETE - SAMPLE SELECTOR UNRESOLVED.
