# Diagnostics Analysis Migration Phase 4.5-C2-A

## Status

REVIEWED

## Summary

Phase 4.5-C2-A migrates the diagnostics and analysis features that were
previously legacy Playground-only into the official IDE at
`apps/reasonscript-ide/ui`.

Migrated features:

- Strict diagnostics
- Cycle diagnostics
- Exhaustiveness
- Type coverage
- Ownership analysis
- Determinism
- Complexity

The implementation derives view state from `/api/analyze` data already
carried by the official IDE project state. No new legacy dedicated endpoint
dependency is introduced.

## Data Contract

The official IDE uses a normalized view model in
`apps/reasonscript-ide/ui/src/viewModels/analysisDiagnostics.ts`.

The model searches optional data from:

- `response.views.strict_diagnostics`
- `response.views.cycle`
- `response.views.exhaustiveness`
- `response.views.type_coverage`
- `response.views.ownership`
- `response.views.determinism`
- `response.views.complexity`
- `response.diagnostics`
- `response.artifacts`
- `response.analyzer`

Missing or malformed optional sections are treated as unavailable. The UI
must not throw when analysis sections are absent.

## Problems Integration

The existing `Problems` bottom tool window now includes migrated analysis
diagnostics for:

- strict diagnostics
- cycle diagnostics
- exhaustiveness diagnostics
- type coverage warnings
- ownership warnings
- determinism warnings or failures
- complexity threshold warnings

Compiler diagnostics remain preserved.

## Overview Integration

The existing `Overview` right inspector tab now includes an analysis summary
for:

- Strict
- Cycle
- Exhaustiveness
- Type Coverage
- Ownership
- Determinism
- Complexity

No new top-level right inspector tab is added.

## Empty State Policy

The official IDE displays stable fallback states when analysis data is
missing:

- No strict diagnostics reported.
- No cycle diagnostics reported.
- No exhaustiveness data available.
- Type coverage unavailable.
- Ownership analysis unavailable.
- Determinism data unavailable.
- Complexity metrics unavailable.

## Deletion Gate Impact

Phase 4.5-C2-A advances the deletion gate, but physical deletion remains
blocked.

Deletion Gate: PARTIALLY MIGRATED - NOT CLOSED.

Still blocking deletion:

- Runtime IO output
- Input state
- Calculation panel
- Runtime trace
- Export / Import / Diff
- Audit / Language audit matrix
- Sample selector remains `DEFERRED`
- deletion-after-removal validation has not run
