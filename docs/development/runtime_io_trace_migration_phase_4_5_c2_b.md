# Runtime IO Trace Migration Phase 4.5-C2-B

## Status

REVIEWED

## Summary

Phase 4.5-C2-B migrates runtime observability features from the legacy
Playground UI into the official IDE at `apps/reasonscript-ide/ui`.

Migrated features:

- Runtime IO output
- Input state
- Calculation panel
- Runtime trace

The implementation derives view state from `/api/analyze` data already
carried by the official IDE project state. No legacy dedicated endpoint
dependency is introduced.

## Data Contract

The official IDE uses a normalized runtime view model in
`apps/reasonscript-ide/ui/src/viewModels/runtimeObservability.ts`.

The model searches optional data from:

- `response.views.runtime_operations`
- `response.views.runtime_trace`
- `response.views.input_state`
- `response.views.calculation`
- `response.views.output`
- `response.views.simulation`
- `response.artifacts.simulation.json`
- `response.artifacts.execution_plan.json`
- `response.artifacts.reason_ir.json`
- `response.pipeline.simulation`
- `response.pipeline.execution_plan`
- `response.simulation`
- `response.runtime_operations`
- `response.output_events`
- `response.input_state`
- `response.calculations`
- `response.analyzer`

Missing or malformed optional sections are treated as unavailable or empty.
The UI must not throw when runtime sections are absent.

## Output Integration

The existing `Output` bottom tool window now includes runtime output events:

- print output
- output events
- input projection messages
- runtime operation logs, when explicitly reported

The Output tool window does not display compiler diagnostics or raw JSON.

## Simulation Integration

The existing `Simulation` right inspector tab now includes:

- existing simulation trace
- runtime trace
- input state
- calculation trace

When runtime trace is missing but simulation trace exists, the runtime trace
section uses simulation trace fallback and labels it explicitly.

## Empty State Policy

The official IDE displays stable fallback states when runtime data is
missing:

- No runtime output reported.
- No input state reported.
- No calculation details reported.
- No runtime trace reported.
- Runtime trace unavailable; showing simulation trace fallback.
- Runtime trace unavailable.

## Deletion Gate Impact

Phase 4.5-C2-B advances the deletion gate, but physical deletion remains
blocked.

Deletion Gate: RUNTIME MIGRATED - NOT CLOSED.

Still blocking deletion:

- Export / Import / Diff
- Audit / Language audit matrix
- Sample selector remains `DEFERRED`
- deletion-after-removal validation has not run
