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

The canonical entry point for repository validation is:

```sh
reason ci
```

Individual commands remain available as implementation-level interfaces for diagnosis, debugging, and incremental development:

```sh
reason workspace
reason check
reason analyze
reason run
reason artifacts
reason validate-artifacts
reason golden
reason agent-protocol
reason agent-report
```

Optional commands:

```sh
reason summary
reason manifest
reason index
reason export
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

## Development Environment

`reason ci` requires the packages in `requirements-dev.txt` (pydantic,
pytest, fastapi, ...) installed into the *same* Python interpreter used to
invoke `reason`. A system Python, or an unrelated sandboxed venv that does
not have these packages installed, will fail either at import time
(`ModuleNotFoundError`, e.g. missing `pydantic`) or during the Tests phase
(`CI-008`, missing `pytest`).

A `Dockerfile` is provided at the repository root that reproduces the same
environment used by `.github/workflows/ci.yml` and `test.yml` (Rust
toolchain, system libraries, and `requirements-dev.txt` installed into a
dedicated venv). Coding agents running in a container should build and use
it instead of an ad-hoc host interpreter:

```sh
docker build -t reasonscript-dev .
docker run --rm -v "$PWD:/workspace" reasonscript-dev ./reason ci --json
```

If running outside the container, install dev dependencies into whichever
interpreter you invoke `reason` with:

```sh
python3 -m pip install -r requirements-dev.txt
```

## CI Stabilization

This repository follows `reasonscript-ci/1.0` for CI execution. The canonical workflow runs:

1. Checkout Repository
2. Environment Setup
3. Workspace Validation
4. Diagnostics Validation
5. Artifact Validation
6. Golden Tests
7. Agent Protocol Validation
8. Compatibility Verification
9. Unit / Integration Tests
10. Completion Report

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

## Canonical CI Entry Point

This repository follows `reasonscript-ci-entry/1.0`. Beginning with ReasonScript Development Platform v0.5, `reason ci` is the single official validation command for local development, Coding Agents, and CI. Individual commands remain implementation-level interfaces and do not replace it.

### Coding Agent Policy

Coding Agents shall execute `reason ci` before reporting task completion. Execution of individual commands is permitted for diagnosis, debugging, or incremental development but does not replace the canonical validation workflow.

### CI Policy

GitHub Actions and equivalent CI systems shall invoke `reason ci` as the primary validation command. Platform-specific scripts shall not duplicate the validation pipeline unless required for infrastructure reasons.

### Entry Point Validation Rules

- `CE-001`: Missing CI pipeline
- `CE-002`: Invalid execution order
- `CE-003`: Required validation omitted
- `CE-004`: Report generation failure
- `CE-005`: Pipeline termination failure

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
