# ReasonScript Development Environment Phase 7.5

## Agent Development Protocol Specification v1.0

Status: DRAFT

Target Release: ReasonScript Development Platform v0.5

Specification ID: `reasonscript-agent-protocol/1.0`

## Purpose

This specification defines the canonical development protocol for coding agents working on the ReasonScript codebase.

The protocol standardizes task execution, validation, artifact generation, regression testing, reporting, and completion criteria to keep development deterministic and reproducible.

## Goals

- deterministic development workflow
- reproducible task execution
- standardized validation
- automatic artifact verification
- regression safety
- machine-readable reports

## Design Principles

Agent workflows are deterministic, reproducible, idempotent, specification-driven, validation-first, and implementation-independent.

## Canonical Workflow

1. Specification
2. Implementation
3. Validation
4. Artifact Verification
5. Golden Tests
6. Completion Report

Agents execute every phase in order.

## Task Structure

Every development task contains:

- Task ID
- Specification
- Scope
- Expected Outputs
- Validation Criteria
- Completion Criteria

## Task States

Supported states:

- `DRAFT`
- `IN_PROGRESS`
- `IMPLEMENTED`
- `VALIDATED`
- `COMPLETED`
- `REJECTED`

State transitions are monotonic.

## Standard Command Sequence

Minimum:

```sh
reason check
reason analyze
reason run
reason artifacts
reason validate-artifacts
reason golden
```

Optional:

```sh
reason summary
reason workspace
reason manifest
reason index
```

## Validation Requirements

Every task executes:

- workspace validation
- diagnostics validation
- artifact validation
- golden tests

No task may be marked `VALIDATED` without passing all required validations.

## Completion Report

Every completed task produces:

- Completion Summary
- Implemented Features
- Validation Results
- Generated Artifacts
- Compatibility Notes
- Remaining Work

## Agent Report

Canonical report:

```json
{
  "task": "Phase 7.5",
  "status": "VALIDATED",
  "tests_passed": 39,
  "artifacts_generated": true
}
```

## Failure Handling

If validation fails:

- stop the current task,
- record diagnostics,
- preserve generated artifacts,
- do not update golden baselines automatically.

Failures do not invalidate previous successful tasks.

## Artifact Policy

Agents do not manually edit generated artifacts. Artifacts are regenerated through official commands only.

Generated artifacts conform to:

- `reasonscript-artifacts/1.0`
- `reasonscript-diagnostics/1.0`

## Golden Policy

Golden baselines are updated only when:

- the specification changes,
- behavior changes intentionally, or
- compatibility policy permits the update.

Updating a golden baseline requires an accompanying specification or changelog update.

## Repository Structure

The repository includes:

- `AGENTS.md`
- `docs/specifications/`
- `docs/changelog/`
- `golden/`
- `tests/`
- `examples/`

`AGENTS.md` defines the operational workflow for coding agents.

## AGENTS.md Requirements

At minimum, `AGENTS.md` defines:

- development workflow
- required commands
- validation sequence
- artifact policy
- golden policy
- completion criteria
- reporting format

## Validation Rules

- `AP-001`: Missing specification
- `AP-002`: Missing validation
- `AP-003`: Missing artifacts
