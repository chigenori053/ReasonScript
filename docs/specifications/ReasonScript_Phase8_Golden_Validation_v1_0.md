# ReasonScript Phase 8 Final - End-to-End Golden Validation v1.0

## Status

IMPLEMENTED

## Version

`reasonscript-phase8-golden-validation/1.0`

## Purpose

Phase 8 Final freezes the end-to-end reproducibility of the reasoning artifact pipeline:

```text
ReasonScript Source
  -> Existing Pipeline
  -> ReasoningModel
  -> ReasoningEvaluationReport
  -> ReasoningRuntimeResult
  -> Golden Validation
```

This phase does not add source syntax, parser behavior, or runtime execution semantics.

## v0.5 Scope

v0.5 core is a CLI-first, artifact-first reasoning model development foundation. It includes the ReasoningModel, ReasoningEvaluationReport, and ReasoningRuntimeResult contracts, deterministic serialization, CLI validation, CI compatibility, and golden artifact validation.

v0.5 core does not include final IDE architecture, final Playground UX, Input Semantic Decomposition, WorldModel integration, autonomous model training, or a general-purpose AI model.

Phase 8D Playground Reasoning Overview is retained as:

```text
Status: VALIDATED
Release Scope: EXPERIMENTAL
v0.5 Core Blocking: false
```

## Golden Scenarios

Golden fixtures live under `examples/v0_8/reasoning_runtime/`:

- `animal_isa.rsn`
- `calculation_chain.rsn`
- `function_return.rsn`
- `branch_selection.rsn`
- `unreachable_goal.rsn`
- `invalid_parse.rsn`

Approved golden artifacts live under `tests/fixtures/golden/phase8/`.

Valid scenarios include:

- `reasoning_model.json`
- `reasoning_evaluation_report.json`
- `reasoning_runtime_result.json`

`invalid_parse` includes `reasoning_runtime_result.json` because model and evaluation artifacts cannot be generated from the fatal pipeline result.

## Validation Rules

Phase 8 Final validates:

- golden source fixture existence
- golden artifact existence
- ReasoningModel schema validation
- ReasoningEvaluationReport schema validation
- ReasoningRuntimeResult schema validation
- exact canonical JSON match between generated and golden artifacts
- deterministic serialization
- CLI JSON output stability
- CI compatibility target registration

Golden validation diagnostics use the `GV-*` family:

- `GV-001`: missing golden source fixture
- `GV-002`: missing golden ReasoningModel artifact
- `GV-003`: missing golden ReasoningEvaluationReport artifact
- `GV-004`: missing golden ReasoningRuntimeResult artifact
- `GV-005`: generated ReasoningModel does not match golden
- `GV-006`: generated ReasoningEvaluationReport does not match golden
- `GV-007`: generated ReasoningRuntimeResult does not match golden
- `GV-008`: generated artifact failed schema validation
- `GV-009`: deterministic serialization mismatch
- `GV-010`: CLI output mismatch
- `GV-011`: unsupported or missing golden scenario
- `GV-012`: unstable metadata detected

## CLI

The canonical validation entry point remains:

```sh
reason ci --json
```

Phase 8 golden validation is also available through:

```sh
reason phase8-golden validate --json
```

Golden artifacts are generated through:

```sh
reason phase8-golden update --json
```

## Compatibility

This phase preserves:

- parser behavior
- runtime execution behavior
- Reason IR execution semantics
- ExecutionPlan semantics
- Simulation semantics
- Knowledge semantics
- `reasonscript-reasoning-model/1.0`
- `reasonscript-reasoning-evaluation-report/1.0`
- `reasonscript-reasoning-runtime-prototype/1.0`
