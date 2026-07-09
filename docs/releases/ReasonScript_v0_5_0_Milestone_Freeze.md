# ReasonScript v0.5.0 Milestone Freeze

## Status

VALIDATED

## Version

`reasonscript-v0.5.0-release-freeze/1.0`

## Frozen Release Definition

ReasonScript v0.5 is a CLI-first, artifact-first reasoning model development foundation.

Japanese fixed definition:

```text
ReasonScript v0.5 は、CLI優先・artifact優先の推論モデル開発基盤である。
```

Normative definition version:

```text
reasonscript-v0.5-release-definition/1.0
```

## Frozen Branch

```text
release/language-surface-v0.5
```

## Frozen Tag

```text
v0.5.0
```

## Frozen Commit

The frozen commit is the commit referenced by annotated tag `v0.5.0`.

## Validation Summary

Required release freeze validation:

```text
./reason phase8-golden validate --json
python3 -m toolchain ci-entry --json
python3 -m pytest tests/golden/test_phase8_golden_validation.py tests/reasoning_model/test_reasoning_runtime_prototype.py -q
./reason ci --json
python3 -m pytest tests -q
```

Observed result:

```text
./reason phase8-golden validate --json: PASS, 6 scenarios passed
python3 -m toolchain ci-entry --json: PASS
python3 -m pytest tests/golden/test_phase8_golden_validation.py tests/reasoning_model/test_reasoning_runtime_prototype.py -q: PASS, 41 passed
./reason ci --json: PASS, 779 tests passed
python3 -m pytest tests -q: PASS, 779 passed
```

## Core Artifact Contracts

- `reasonscript-reasoning-model/1.0`
- `reasonscript-reasoning-evaluation-report/1.0`
- `reasonscript-reasoning-runtime-prototype/1.0`
- `reasonscript-phase8-golden-validation/1.0`
- `reasonscript-v0.5-release-stabilization/1.0`
- `reasonscript-v0.5-release-definition/1.0`

## Non-Core Experimental Features

- Phase 8D Playground Reasoning Overview

Phase 8D status:

```text
VALIDATED / EXPERIMENTAL / NON-BLOCKING
```

It may remain in the repository and CI, but it does not redefine v0.5.0 as an IDE release.

## Future Work Boundary

Future Phase 9 or post-v0.5 work may add new conceptual or compatibility-changing capabilities only under a later version or phase.

ReasonScript v0.5.0 is frozen as the validated CLI-first, artifact-first reasoning model development foundation.

Future work must not redefine v0.5.0. Any new conceptual or compatibility-changing work must target a later version or phase.
