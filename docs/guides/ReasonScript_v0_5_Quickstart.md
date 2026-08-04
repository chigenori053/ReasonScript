# ReasonScript v0.5 Quickstart

## Purpose

This guide shows the minimum v0.5 workflow for validating the repository and generating Phase 8 reasoning artifacts.

## 1. Clone Repository

```sh
git clone git@github.com:chigenori053/ReasonScript.git
cd ReasonScript
```

## 2. Select Branch

```sh
git checkout release/language-surface-v0.5
```

## 3. Run Canonical CI

```sh
./reason ci --json
```

## 4. Run Phase 8 Golden Validation

```sh
./reason phase8-golden validate --json
```

## 5. Generate a Runtime Result

```sh
./reason reasoning-runtime run examples/v0_8/reasoning_runtime/animal_isa.rsn --json
```

## 6. Generate Model and Evaluation Artifacts

```sh
./reason reasoning-runtime build-model examples/v0_8/reasoning_runtime/animal_isa.rsn --json
./reason reasoning-runtime evaluate examples/v0_8/reasoning_runtime/animal_isa.rsn --json
```

## 7. Inspect and Validate Artifacts

The runtime command emits a `ReasoningRuntimeResult` JSON document. Save generated JSON only when intentionally creating or reviewing artifacts.

Validate runtime results with:

```sh
./reason reasoning-runtime validate <runtime-result.json> --json
```

Validate generated model and evaluation report artifacts with:

```sh
./reason reasoning-model validate <reasoning-model.json> --json
./reason reasoning-eval validate <evaluation-report.json> --json
```

## Controlled Maintenance

`./reason phase8-golden update --json` regenerates approved golden artifacts. Use it only for intentional behavior changes with a matching specification or changelog update.
