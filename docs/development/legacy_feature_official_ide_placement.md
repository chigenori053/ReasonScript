# Legacy Feature Official IDE Placement

## Status

REVIEWED for Phase 4.5-C.

This document defines placement policy only. It does not add new top-level
right inspector tabs and does not implement migrated panels.

## Summary

Migrated legacy features must fit the existing Standard IDE Layout:

- Right Inspector: `Overview`, `Plan`, `Simulation`, `Knowledge`,
  `Artifacts`
- Bottom Tool Window: `Problems`, `Output`, `Logs`, `Tests`

The migration must preserve these top-level names. Legacy features should be
placed as sections, panels, diagnostics groups, artifact entries, or tool
window content inside the existing layout.

Phase 4.5-C2-A migrates strict diagnostics, cycle diagnostics,
exhaustiveness, type coverage, ownership analysis, determinism, and
complexity into the existing `Overview` and `Problems` surfaces.

Phase 4.5-C2-B migrates runtime IO output, input state, calculation trace,
and runtime trace into the existing `Output`, `Simulation`, and `Overview`
surfaces.

Phase 4.5-C2-C migrates export, import, and diff into the existing
`Artifacts`, `Overview`, `Problems`, and `Output` surfaces. The dedicated
artifact operation APIs remain available; their backend contracts are not
rewritten by the official IDE migration.

Phase 4.5-C2-D migrates Audit and Language audit matrix into the existing
`Overview`, `Tests`, `Problems`, `Artifacts`, and `Output` surfaces. The
dedicated language audit APIs remain available; their backend contracts are
not rewritten by the official IDE migration.

Phase 4.5-C2-E migrates Sample selector into the existing Workspace Explorer,
`Problems`, `Output`, and `Artifacts` surfaces as Sample Browser / Example
Loader. The existing `/api/examples` contract remains available and is not
rewritten by the official IDE migration.

## Standard Layout Policy

- Do not add new top-level right inspector tabs for legacy-only features.
- Do not recreate the legacy Playground layout inside the official IDE.
- Prefer `/api/analyze`-derived data for read-only analysis views.
- Use dedicated APIs only for explicit artifact operations such as export,
  import, diff, audit export, or backend-only regression workflows.
- The legacy Playground layout no longer exists; do not reintroduce it.

Allowed top-level right inspector tabs:

- `Overview`
- `Plan`
- `Simulation`
- `Knowledge`
- `Artifacts`

Allowed bottom tool windows:

- `Problems`
- `Output`
- `Logs`
- `Tests`

## Right Inspector Placement

| Existing tab | Migrated content |
|---|---|
| `Overview` | Audit summary, determinism summary, complexity summary, ownership summary, type coverage summary, artifact workflow summary |
| `Plan` | Dependency graph, cycle diagnostics, execution path analysis |
| `Simulation` | Runtime trace, input state, calculation trace, runtime operations |
| `Knowledge` | Evidence, path signature, knowledge emergence detail |
| `Artifacts` | AST, Semantic AST, Reason IR, ExecutionPlan, Simulation JSON, Knowledge JSON, export/import/diff sections, raw audit report, raw language audit matrix JSON, audit export result, sample metadata |

## Bottom Tool Window Placement

| Existing tool window | Migrated content |
|---|---|
| `Problems` | Strict diagnostics, cycle diagnostics, exhaustiveness diagnostics, type coverage warnings, import validation errors, diff compatibility warnings, audit failures, disconnected language audit rows, sample load errors |
| `Output` | Runtime IO output, print/input state projection, runtime logs, export/import/diff operation logs, audit operation logs, sample load logs |
| `Logs` | Analyzer, backend, and runtime log streams |
| `Tests` | Language audit matrix; optional regression summaries if backend-only workflows later receive a UI surface |

## Artifacts Placement

Artifact-oriented legacy features should be placed inside the existing
`Artifacts` right inspector tab:

- Export
- Import
- Diff
- Audit export, if retained as a UI operation
- Sample metadata
- AST
- Semantic AST
- Reason IR
- ExecutionPlan
- Simulation JSON
- Knowledge JSON

The artifact area may expose commands for artifact portability and
comparison, but it must not introduce a new top-level inspector tab.

Import uses validation-first handling in the official IDE. Destructive
overwrite requires an explicit future policy; failed imports must not mutate
the selected editor file silently.

Audit raw report, raw matrix JSON, and audit export result remain available in
Artifacts. The matrix itself is primarily displayed in Tests.

## Not Placed / Deprecated Features

Backend-only in Phase 4.5-C:

- Run all
- Baseline
- Regression runner

Deferred:

- None. Sample selector was migrated in Phase 4.5-C2-E.

Deprecated in Phase 4.5-C:

- None

No feature is approved for removal solely by this placement policy. Deferred
and backend-only items were resolved before Phase 4.5-D physically removed
the legacy Playground frontend.

Phase 4.5-D removed the legacy Playground frontend.

The active official IDE UI is:

- `apps/reasonscript-ide/ui`

The legacy UI path no longer exists:

- `playground/frontend`

This document now records placement policy for migrated features only.
