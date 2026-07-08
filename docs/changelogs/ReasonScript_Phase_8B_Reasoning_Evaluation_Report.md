# ReasonScript Phase 8B — Reasoning Evaluation Report v1.0

## Status

VALIDATED

## Version

`reasonscript-reasoning-evaluation-report/1.0`

## Depends On

`reasonscript-reasoning-model/1.0`

## Added

- Added versioned ReasoningEvaluationReport contract.
- Added ReasoningEvaluationReport JSON schema.
- Added evaluator for Phase 8A ReasoningModel artifacts.
- Added report validator.
- Added deterministic JSON serialization.
- Added reachability check.
- Added determinism check.
- Added evidence completeness check.
- Added consistency check.
- Added minimality check.
- Added branch traceability check.
- Added `reason reasoning-eval evaluate <reasoning-model.json> --json`.
- Added `reason reasoning-eval validate <evaluation-report.json> --json`.
- Added CI compatibility target for `reasonscript-reasoning-evaluation-report/1.0`.

## Unchanged

- Parser behavior is unchanged.
- Runtime execution behavior is unchanged.
- Reason IR execution semantics are unchanged.
- ExecutionPlan semantics are unchanged.
- Simulation semantics are unchanged.
- Knowledge semantics are unchanged.
- Existing ReasoningModel contract remains unchanged.

## Phase Result

Phase 8B — VALIDATED
