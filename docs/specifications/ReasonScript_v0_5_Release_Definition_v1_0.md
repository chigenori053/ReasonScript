# ReasonScript v0.5 Release Definition Specification

## Status

FIXED

## Version

`reasonscript-v0.5-release-definition/1.0`

## Release Target

ReasonScript v0.5

## Fixed Release Definition

ReasonScript v0.5 is a CLI-first, artifact-first reasoning model development foundation.

Japanese fixed definition:

```text
ReasonScript v0.5 は、CLI優先・artifact優先の推論モデル開発基盤である。
```

## Purpose

This specification fixes the official release definition of ReasonScript v0.5.

ReasonScript v0.5 is not defined as an IDE release, an autonomous AI system, or a general-purpose model training framework.

It is defined as the first stable development baseline for generating, validating, evaluating, serializing, and regression-testing reasoning model artifacts from supported ReasonScript sources.

## Core Scope

ReasonScript v0.5 core includes:

- ReasoningModel artifact generation
- ReasoningEvaluationReport artifact generation
- ReasoningRuntimeResult artifact generation
- JSON schema validation
- contract validation
- deterministic serialization
- golden validation
- CLI-based validation workflow
- canonical CI entry point
- Coding Agent development workflow

The core pipeline is:

```text
ReasonScript Source
  -> Existing Pipeline
  -> ReasoningModel
  -> ReasoningEvaluationReport
  -> ReasoningRuntimeResult
  -> Golden Validation
  -> CI Validation
```

## Core Artifact Contracts

ReasonScript v0.5 core is based on:

- `reasonscript-reasoning-model/1.0`
- `reasonscript-reasoning-evaluation-report/1.0`
- `reasonscript-reasoning-runtime-prototype/1.0`
- `reasonscript-phase8-golden-validation/1.0`
- `reasonscript-v0.5-release-stabilization/1.0`

These contracts define the artifact-first foundation of v0.5.

## Official CLI Workflow

The canonical validation command is:

```sh
./reason ci --json
```

Additional supported commands include:

```sh
./reason phase8-golden validate --json
./reason phase8-golden update --json
./reason reasoning-model validate <file> --json
./reason reasoning-eval evaluate <reasoning-model.json> --json
./reason reasoning-eval validate <evaluation-report.json> --json
./reason reasoning-runtime run <source.rsn> --json
./reason reasoning-runtime build-model <source.rsn> --json
./reason reasoning-runtime evaluate <source.rsn> --json
./reason reasoning-runtime validate <runtime-result.json> --json
```

`phase8-golden update` is a controlled maintenance command. It must not be treated as a normal validation command.

## Validation Baseline

```text
./reason phase8-golden validate --json
  PASS

python3 -m toolchain ci-entry --json
  PASS

python3 -m pytest tests/golden/test_phase8_golden_validation.py tests/reasoning_model/test_reasoning_runtime_prototype.py -q
  PASS, 41 passed

./reason ci --json
  PASS, 779 tests passed

python3 -m pytest tests -q
  PASS, 779 passed
```

Optional experimental IDE validation:

```text
python3 -m pytest tests/playground/test_reasoning_overview_backend.py -q
  PASS, 15 passed

npm run build --prefix apps/reasonscript-ide/ui
  PASS
```

## Out of Scope

ReasonScript v0.5 core does not include final IDE architecture, final Playground UX, Input Semantic Decomposition, natural language semantic decomposition, image/audio/multimodal input decomposition, WorldModel integration, autonomous model training, general-purpose AI model behavior, or a production deployment platform.

## Phase 8D Handling

Phase 8D Playground Reasoning Overview is retained as:

```text
Status: VALIDATED
Release Scope: EXPERIMENTAL
v0.5 Core Blocking: false
```

Phase 8D is validated as an experimental visualization layer.

It is not part of the v0.5 core completion criteria.  
ReasonScript v0.5 remains a CLI-first, artifact-first reasoning model development foundation.

Phase 8D may remain in the repository and CI, but v0.5 must not be defined as an IDE release.

## Compatibility Guarantees

ReasonScript v0.5 preserves parser behavior, runtime execution behavior, Reason IR execution semantics, ExecutionPlan semantics, Simulation semantics, Knowledge semantics, ReasoningModel contract, ReasoningEvaluationReport contract, ReasoningRuntimeResult contract, and Phase 8 golden validation behavior.

Any future breaking change must be deferred to a later version and documented separately.

## Coding Agent Development Policy

ReasonScript v0.5 supports Coding Agent implementation through a spec-first workflow:

1. Read the target specification.
2. Identify in-scope and out-of-scope files.
3. Implement contract-first.
4. Add or update JSON schema when required.
5. Add validator coverage when required.
6. Add CLI wrapper when required.
7. Add fixtures.
8. Add tests.
9. Update changelog and release documentation.
10. Run targeted tests.
11. Run `./reason ci --json`.
12. Preserve parser, runtime, Reason IR, ExecutionPlan, Simulation, and Knowledge compatibility unless explicitly scoped.

Forbidden behavior:

- Do not silently change parser semantics.
- Do not silently change runtime execution semantics.
- Do not alter Reason IR behavior without a specification.
- Do not bypass `./reason ci --json`.
- Do not mix IDE experimental changes into v0.5 core commits.
- Do not regenerate golden artifacts without explicit reason.

## Known Limitations

- v0.5 supports structured reasoning artifacts, not general autonomous reasoning.
- v0.5 does not implement Input Semantic Decomposition as core.
- v0.5 does not decompose natural language input into semantic units.
- v0.5 does not include WorldModel integration.
- v0.5 does not include a final production IDE.
- v0.5 does not claim semantic truth in the external world.
- EvaluationReport validates artifact-level reasoning properties.
- Golden validation covers selected supported scenarios, not all possible language programs.

## Release Success Statement

ReasonScript v0.5 successfully establishes a CLI-first, artifact-first reasoning model development foundation.

It supports generation, validation, evaluation, deterministic serialization, and golden regression validation of reasoning artifacts from supported ReasonScript sources through the canonical `./reason ci --json` entry point.

## Final Definition

ReasonScript v0.5 is fixed as:

```text
ReasonScript v0.5 is a CLI-first, artifact-first reasoning model development foundation.
```

Japanese fixed definition:

```text
ReasonScript v0.5 は、CLI優先・artifact優先の推論モデル開発基盤である。
```

This definition is the official baseline for all v0.5 documentation, validation reports, release notes, and future roadmap planning.
