# ReasonScript v0.5 CLI Reference

## Canonical CI

```sh
./reason ci --json
```

Runs the canonical v0.5 validation pipeline.

## Phase 8 Golden Validation

```sh
./reason phase8-golden validate --json
```

Validates Phase 8 golden fixtures and generated reasoning artifacts.

```sh
./reason phase8-golden update --json
```

Controlled maintenance command. Use only when intentionally updating approved golden artifacts after a specification, compatibility policy, or intentional behavior change.

## ReasoningModel

```sh
./reason reasoning-model validate <file> --json
```

Validates a `reasonscript-reasoning-model/1.0` artifact.

## ReasoningEvaluationReport

```sh
./reason reasoning-eval evaluate <reasoning-model.json> --json
./reason reasoning-eval validate <evaluation-report.json> --json
```

Evaluates a ReasoningModel or validates an existing `reasonscript-reasoning-evaluation-report/1.0` artifact.

## ReasoningRuntimeResult

```sh
./reason reasoning-runtime run <source.rsn> --json
./reason reasoning-runtime build-model <source.rsn> --json
./reason reasoning-runtime evaluate <source.rsn> --json
./reason reasoning-runtime validate <runtime-result.json> --json
```

Generates, evaluates, or validates Phase 8 runtime reasoning artifacts.
