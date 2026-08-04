# ReasonScript Reasoning Runtime Prototype v1.0

## Status

VALIDATED FOR PHASE 8C

## Version

`reasonscript-reasoning-runtime-prototype/1.0`

## Purpose

Phase 8C adds a prototype artifact generation layer above the existing ReasonScript pipeline. It consumes existing pipeline artifacts, projects them into a Phase 8A `ReasoningModel`, evaluates that model with the Phase 8B evaluator, and emits a `ReasoningRuntimeResult`.

## Runtime Result

`ReasoningRuntimeResult` contains:

- `schema_version`
- `run_id`
- `source_ref`
- `pipeline_status`
- `reasoning_model`
- `evaluation_report`
- `diagnostics`
- optional `metadata`

The schema version is `reasonscript-reasoning-runtime-prototype/1.0`.

## Flow

```text
ReasonScript source
  -> existing pipeline execution
  -> collect pipeline artifacts
  -> build ReasoningModel
  -> validate ReasoningModel
  -> evaluate ReasoningModel
  -> validate ReasoningEvaluationReport
  -> emit ReasoningRuntimeResult
```

## Compatibility

Phase 8C does not introduce syntax and does not change parser behavior, runtime execution behavior, Reason IR semantics, ExecutionPlan semantics, Simulation semantics, Knowledge semantics, the Phase 8A ReasoningModel contract, or the Phase 8B ReasoningEvaluationReport contract.

## CLI

```sh
./reason reasoning-runtime run <source.rsn> --json
./reason reasoning-runtime build-model <source.rsn> --json
./reason reasoning-runtime evaluate <source.rsn> --json
./reason reasoning-runtime validate <runtime-result.json> --json
```

## Diagnostics

Phase 8C diagnostics use `RRP-*` codes. Pipeline availability diagnostics include `RRP-PIPE-002` for missing Reason IR, `RRP-PIPE-003` for missing ExecutionPlan, `RRP-PIPE-004` for missing Simulation, and `RRP-PIPE-005` for missing Knowledge.

## Determinism

Runtime results serialize in canonical field order. Nested ReasoningModel and ReasoningEvaluationReport artifacts use their Phase 8A and Phase 8B canonical serializers.

## Validation

Phase 8C has been validated with:

```text
python3 -m pytest tests/reasoning_model -q
91 passed

./reason ci --json
PASS
754 tests passed
```

CLI `run`, `build-model`, `evaluate`, and `validate` were confirmed.

## Phase Result

```text
Phase 8C - COMPLETE
Phase 8C - VALIDATED
```
