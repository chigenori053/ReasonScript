# Legacy Feature Migration / Deprecation Decision

## Status

REVIEWED - UPDATED THROUGH PHASE 4.5-C2-E.

This document began as a Phase 4.5-C decision record.
It now also tracks post-decision migration status for migrated legacy
features.

## Summary

Phase 4.5-C classifies legacy-only Playground UI features before physical
removal can be considered. The official IDE remains
`apps/reasonscript-ide/ui`; `playground/frontend` remains present until the
migration and deletion gates are satisfied.

The current deletion gate is:

ALL LEGACY FEATURE DECISIONS RESOLVED - READY FOR PHYSICAL REMOVAL PLANNING.

Physical deletion is explicitly out of scope for this phase and remains NOT
CLOSED.

## Decision Categories

- `ALREADY_SUPPORTED`: the official IDE already has equivalent user-facing
  behavior.
- `MIGRATE_REQUIRED`: the feature must be implemented in the official IDE
  before legacy UI deletion.
- `MIGRATED`: the feature has been migrated into the official IDE after the
  original Phase 4.5-C decision.
- `DEPRECATE_ALLOWED`: the feature may be removed with the legacy UI after
  recording its replacement and timing.
- `BACKEND_ONLY`: the UI can be removed, but backend/API/CLI/test utility
  behavior remains.
- `DEFERRED`: no final product decision has been made; this must be resolved
  before physical deletion.
- `MIGRATE_WITH_ANALYZE_DERIVED_DATA`: the migrated official IDE surface
  should be backed by `/api/analyze` response data rather than retaining a
  dedicated legacy UI flow.

## Feature Decision Matrix

| Feature | Legacy source | Official IDE status | Decision | Rationale |
|---|---|---|---|---|
| Analyze | `playground/frontend` analyze flow | Supported | `ALREADY_SUPPORTED` | The official IDE already calls `/api/analyze`. |
| Run | `playground/frontend` run flow | Supported via runtime operations | `ALREADY_SUPPORTED` | Runtime operations are derived from official analysis state. |
| Validate | `playground/frontend` validate flow | Supported differently | `ALREADY_SUPPORTED` | `ValidationView` covers validation from analysis-derived data. |
| Audit | `LanguageAuditPanel` / audit flow | Migrated in Phase 4.5-C2-D | `MIGRATED` | IDE quality and verification workflow is surfaced in Overview, Problems, Output, and Artifacts. |
| Runtime IO output | Console / `OutputPanel` | Migrated in Phase 4.5-C2-B | `MIGRATED` | Runtime output events are now surfaced in the official Output tool window. |
| Input state | `InputStatePanel` | Migrated in Phase 4.5-C2-B | `MIGRATED` | Stateful input inspection is now surfaced in the official Simulation tab. |
| Calculation panel | `CalculationPanel` | Migrated in Phase 4.5-C2-B | `MIGRATED` | Calculation traces are now surfaced in the official Simulation tab. |
| Cycle diagnostics | `CyclePanel` | Migrated in Phase 4.5-C2-A | `MIGRATED` | Dependency safety diagnostics are now surfaced in Problems and Overview. |
| Runtime trace | `RuntimeTracePanel` | Migrated in Phase 4.5-C2-B | `MIGRATED` | Runtime trace is now surfaced in Simulation with simulation trace fallback. |
| Strict diagnostics | `StrictDiagnosticsPanel` | Migrated in Phase 4.5-C2-A | `MIGRATED` | Strict/Rust-compatible diagnostics are now surfaced in Problems and Overview. |
| Ownership analysis | `OwnershipPanel` | Migrated in Phase 4.5-C2-A | `MIGRATED` | Producer/consumer analysis is now summarized in Overview with Problems fallback. |
| Type coverage | `TypeCoveragePanel` | Migrated in Phase 4.5-C2-A | `MIGRATED` | Coverage percentage and missing type warnings are now surfaced in the official IDE. |
| Exhaustiveness | `ExhaustivenessPanel` | Migrated in Phase 4.5-C2-A | `MIGRATED` | Pattern and enum completeness diagnostics are now surfaced in Problems and Overview. |
| Determinism | `DeterminismPanel` | Migrated in Phase 4.5-C2-A | `MIGRATED` | Determinism status and non-determinism warnings are now surfaced in the official IDE. |
| Complexity | `ComplexityPanel` | Migrated in Phase 4.5-C2-A | `MIGRATED` | Complexity summary and threshold warnings are now surfaced in Overview and Problems. |
| Export | `ExportPanel` | Migrated in Phase 4.5-C2-C | `MIGRATED` | Artifact portability is surfaced in the official Artifacts tab and Output logs. |
| Import | import flow | Migrated in Phase 4.5-C2-C | `MIGRATED` | Artifact/project restoration is surfaced with validation-first handling in the official Artifacts tab. |
| Diff | `DiffPanel` | Migrated in Phase 4.5-C2-C | `MIGRATED` | Pipeline comparison is surfaced in the official Artifacts tab, Overview, Problems, and Output. |
| Language audit matrix | `LanguageAuditPanel` | Migrated in Phase 4.5-C2-D | `MIGRATED` | Language surface integration verification is surfaced in the Tests tool window. |
| Run all | `RegressionRunner` | Not supported | `BACKEND_ONLY` | This is a CI/QA workflow, not a required end-user IDE surface. |
| Baseline | `BaselinePanel` | Not supported | `BACKEND_ONLY` | Regression baselines belong to backend, CLI, or test workflows. |
| Regression runner | `RegressionRunner` | Not supported | `BACKEND_ONLY` | Regression orchestration should remain outside the primary IDE UI. |
| Sample selector | `/api/examples` flow | Migrated in Phase 4.5-C2-E | `MIGRATED` | Sample Browser / Example Loader is surfaced inside the official IDE Workspace Explorer with Problems, Output, and Artifacts integration. |

## Migrate Required

None. All `MIGRATE_REQUIRED` legacy UI features have been migrated.

## Migrated

- Strict diagnostics
- Cycle diagnostics
- Exhaustiveness
- Type coverage
- Ownership analysis
- Determinism
- Complexity
- Runtime IO output
- Input state
- Calculation panel
- Runtime trace
- Export
- Import
- Diff
- Audit
- Language audit matrix
- Sample selector

## Deprecate Allowed

None for Phase 4.5-C. No legacy-only feature is approved for UI deletion
without either migration, backend-only retention, or a later explicit
deprecation record.

## Backend Only

- Run all
- Baseline
- Regression runner

These workflows should remain available through backend APIs, CLI commands,
or test infrastructure while the legacy UI is removed.

## Deferred

None. All previously deferred legacy UI features have been resolved.

## Final Recommendation

All legacy UI migration and decision blockers have been resolved.

Sample selector has been migrated into the official IDE as Sample Browser /
Example Loader.

Do not delete `playground/frontend` until Phase 4.5-D physical removal
planning and deletion-after-removal validation are completed.

Proceed to:

- Phase 4.5-D - Legacy Playground Physical Removal

## Deletion Gate Impact

After this phase:

- legacy-only features have migration or backend-only decisions.
- legacy-only APIs have retention decisions in
  `docs/development/legacy_api_retention_policy.md`.
- official IDE placement is defined in
  `docs/development/legacy_feature_official_ide_placement.md`.

Still NOT enough for physical deletion:

- `playground/frontend` has not been removed.
- deletion-after-removal validation has not run.

Deletion Gate: ALL LEGACY FEATURE DECISIONS RESOLVED - READY FOR PHYSICAL REMOVAL PLANNING.
