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
  "version": "1.0",
  "task": "Phase 7.5",
  "status": "VALIDATED",
  "tests_passed": 39,
  "artifacts_generated": true
}
```

The canonical report is generated as `agent_report.json`.

Completion reports must include:

- Completion Summary
- Implemented Features
- Validation Results
- Generated Artifacts
- Compatibility Notes
- Remaining Work

## CI Stabilization

This repository follows `reasonscript-ci/1.0` for CI execution. The canonical workflow runs:

1. Checkout Repository
2. Environment Setup
3. Workspace Validation
4. Diagnostics Validation
5. Artifact Validation
6. Golden Tests
7. Agent Protocol Validation
8. Unit / Integration Tests
9. Completion Report

Run the full pipeline locally with:

```sh
reason ci --json
```

The pipeline generates `ci_report.json` and `ci_summary.json`. Every validation failure terminates the pipeline and reports the failing phase.

### CI Validation Rules

- `CI-001`: Missing workflow
- `CI-002`: Required command failed
- `CI-003`: Workspace validation failed
- `CI-004`: Diagnostics validation failed
- `CI-005`: Artifact validation failed
- `CI-006`: Golden test failed
- `CI-007`: Agent protocol violation
- `CI-008`: Test failure
- `CI-009`: Compatibility failure
- `CI-010`: Report generation failure

## Protocol Validation Rules

- `AP-001`: Missing specification
- `AP-002`: Missing validation
- `AP-003`: Missing artifacts
- `AP-004`: Golden failure
- `AP-005`: Invalid task state
- `AP-006`: Incomplete completion report
- `AP-007`: Protocol violation
- `AP-008`: Manual artifact modification
- `AP-009`: Required command skipped
- `AP-010`: Unrecorded compatibility change
