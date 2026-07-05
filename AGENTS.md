# ReasonScript Agent Development Protocol

This repository follows `reasonscript-agent-protocol/1.0` for coding-agent work.

## Development Workflow

Agents execute phases in this order:

1. Specification
2. Implementation
3. Validation
4. Artifact verification
5. Golden tests
6. Completion report

Task states are monotonic:

`DRAFT -> IN_PROGRESS -> IMPLEMENTED -> VALIDATED -> COMPLETED`

`REJECTED` is terminal and is used only when the task cannot be completed under the accepted scope.

## Required Commands

Minimum command sequence:

```sh
reason check
reason analyze
reason run
reason artifacts
reason validate-artifacts
reason golden
```

Optional commands:

```sh
reason summary
reason workspace
reason manifest
reason index
```

## Validation Sequence

Every development task must run:

1. Workspace validation
2. Diagnostics validation
3. Artifact validation
4. Golden tests

A task may not be marked `VALIDATED` unless all required validations pass.

## Artifact Policy

Generated artifacts must not be edited manually. Regenerate them through official `reason` commands only.

Generated artifacts must conform to:

- `reasonscript-artifacts/1.0`
- `reasonscript-diagnostics/1.0`

## Golden Policy

Golden baselines may be updated only when:

- a specification changes,
- an intentional behavior change is implemented, or
- compatibility policy permits the update.

Golden baseline updates require a matching specification or changelog update. Do not update golden baselines automatically after validation failure.

## Completion Criteria

A task is complete only when:

- the implementation matches the task specification,
- required validation commands pass,
- generated artifacts validate successfully,
- golden tests pass,
- a completion report records results and remaining work.

## Reporting Format

Canonical machine-readable report:

```json
{
  "task": "Phase 7.5",
  "status": "VALIDATED",
  "tests_passed": 39,
  "artifacts_generated": true
}
```

Completion reports must include:

- Completion Summary
- Implemented Features
- Validation Results
- Generated Artifacts
- Compatibility Notes
- Remaining Work
