# ReasonScript Development Environment Phase 7.5

## Agent Development Protocol Specification v1.0

Status: VALIDATED

Target Release: ReasonScript Development Platform v0.5

Specification ID: `reasonscript-agent-protocol/1.0`

## Purpose

This specification defines the canonical development protocol for coding agents working on the ReasonScript codebase.

The protocol standardizes task execution, validation, artifact generation, regression testing, reporting, and completion criteria to keep development deterministic and reproducible.

This protocol applies to coding agents, CLI tools, CI pipelines, and future orchestration systems.

## Goals

- deterministic development workflow
- reproducible task execution
- standardized validation
- automatic artifact verification
- regression safety
- machine-readable reports
- specification-first development

## Design Principles

Agent workflows are deterministic, reproducible, idempotent, specification-driven, validation-first, and implementation-independent.

Agents always validate work against the project specification before reporting completion.

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
  "version": "1.0",
  "task": "Phase 7.5",
  "status": "VALIDATED",
  "tests_passed": 39,
  "artifacts_generated": true
}
```

The report is generated as `agent_report.json`.

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
- `AP-004`: Golden failure
- `AP-005`: Invalid task state
- `AP-006`: Incomplete completion report
- `AP-007`: Protocol violation
- `AP-008`: Manual artifact modification
- `AP-009`: Required command skipped
- `AP-010`: Unrecorded compatibility change

## CLI Integration

The following commands are defined:

```sh
reason agent-protocol
reason agent-report
```

Existing CLI commands participate in the protocol workflow.

## Determinism Guarantees

The protocol guarantees deterministic command execution, validation, artifact generation, reporting, and task completion.

## Compatibility

Compatible with:

- `reasonscript-workspace/1.0`
- `reasonscript-diagnostics/1.0`
- `reasonscript-artifacts/1.0`
- `reasonscript-golden-tests/1.0`
- `reasonscript-cli/0.5`

## Out of Scope

This specification excludes autonomous task planning, source code generation strategies, AI model selection, multi-agent orchestration, human review workflow, IDE integration, and Frontend SDK.

## Completion Criteria

Phase 7.5 is complete when:

- `AGENTS.md` is implemented and version controlled.
- The canonical development workflow is documented.
- Standard command sequences are implemented.
- Validation requirements are enforced.
- Artifact and Golden policies are enforced.
- Validation rules `AP-001` through `AP-010` are implemented.
- `agent_report.json` is generated in the canonical format.
- Regression tests verify deterministic protocol execution.
- Coding agents can complete development tasks using only the project specifications, the protocol, and the standard CLI.
