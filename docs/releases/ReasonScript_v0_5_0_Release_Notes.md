# ReasonScript v0.5.0 Release Notes

## Status

VALIDATED

## Release Tag

`v0.5.0`

## Branch

`release/language-surface-v0.5`

## Release Definition

ReasonScript v0.5 is a CLI-first, artifact-first reasoning model development foundation.

Japanese fixed definition:

```text
ReasonScript v0.5 は、CLI優先・artifact優先の推論モデル開発基盤である。
```

## Core Capabilities

- ReasoningModel artifact generation
- ReasoningEvaluationReport artifact generation
- ReasoningRuntimeResult artifact generation
- Contract validation
- JSON schema validation
- Deterministic serialization
- Phase 8 golden validation
- CLI-first validation workflow
- Canonical CI through `./reason ci --json`
- Coding Agent spec-first development workflow

## Validated Contracts

- `reasonscript-reasoning-model/1.0`
- `reasonscript-reasoning-evaluation-report/1.0`
- `reasonscript-reasoning-runtime-prototype/1.0`
- `reasonscript-phase8-golden-validation/1.0`
- `reasonscript-v0.5-release-stabilization/1.0`
- `reasonscript-v0.5-release-definition/1.0`

## CLI Commands

Canonical validation:

```sh
./reason ci --json
```

Supported validation and artifact commands:

```sh
./reason phase8-golden validate --json
./reason reasoning-model validate <file> --json
./reason reasoning-eval evaluate <reasoning-model.json> --json
./reason reasoning-eval validate <evaluation-report.json> --json
./reason reasoning-runtime run <source.rsn> --json
./reason reasoning-runtime build-model <source.rsn> --json
./reason reasoning-runtime evaluate <source.rsn> --json
./reason reasoning-runtime validate <runtime-result.json> --json
```

## Golden Scenarios

- `animal_isa`
- `calculation_chain`
- `function_return`
- `branch_selection`
- `unreachable_goal`
- `invalid_parse`

## Experimental Feature

Phase 8D Playground Reasoning Overview is retained as:

- Status: VALIDATED
- Release Scope: EXPERIMENTAL
- v0.5 Core Blocking: false

It is not part of the v0.5 core completion criteria.

## Out of Scope

- final IDE architecture
- Input Semantic Decomposition
- WorldModel integration
- autonomous model training
- general-purpose AI behavior

## Compatibility

ReasonScript v0.5.0 preserves:

- parser behavior
- runtime execution behavior
- Reason IR execution semantics
- ExecutionPlan semantics
- Simulation semantics
- Knowledge semantics
- Phase 8 artifact contracts

## Validation

Final release freeze validation commands:

```text
./reason phase8-golden validate --json
python3 -m toolchain ci-entry --json
python3 -m pytest tests/golden/test_phase8_golden_validation.py tests/reasoning_model/test_reasoning_runtime_prototype.py -q
./reason ci --json
python3 -m pytest tests -q
```

Observed release freeze result:

```text
./reason phase8-golden validate --json: PASS, 6 scenarios passed
python3 -m toolchain ci-entry --json: PASS
python3 -m pytest tests/golden/test_phase8_golden_validation.py tests/reasoning_model/test_reasoning_runtime_prototype.py -q: PASS, 41 passed
./reason ci --json: PASS, 779 tests passed
python3 -m pytest tests -q: PASS, 779 passed
```

## Next

Post-v0.5 development should begin from a new phase or branch, with Phase 9 Input Semantic Decomposition as the recommended next major milestone.
