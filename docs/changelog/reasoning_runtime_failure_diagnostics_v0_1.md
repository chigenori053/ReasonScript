# Reasoning Runtime Failure Diagnostics v0.1

## Status

VALIDATED

## Version

`reasonscript-reasoning-runtime-diagnostics-fix/0.1`

## Base

ReasonScript v0.5.0

## Fixed

- Improved `RRP-PIPE-001` parser/pipeline failure diagnostics.
- Made reasoning-runtime failure diagnostics actionable when parser/pipeline execution fails.
- Made `pipeline_status.diagnostics_count` consistent with emitted diagnostics.
- Clarified that unavailable Reason IR, ExecutionPlan, Simulation, and Knowledge artifacts are consequences of parser/pipeline failure.

## Not Changed

- Parser behavior is unchanged.
- Runtime execution behavior is unchanged.
- Reason IR semantics are unchanged.
- ExecutionPlan semantics are unchanged.
- Simulation semantics are unchanged.
- Knowledge semantics are unchanged.
- Relation declaration semantics are not implemented.

## Validation

- `python3 -m pytest tests/reasoning_model -q`
- `./reason reasoning-runtime run examples/v0_8/reasoning_runtime/animal_isa.rsn --json`
- `./reason reasoning-runtime run tests/fixtures/reasoning_runtime/invalid_relation_chain_probe.rsn --json`
- `./reason ci --json`
