# ReasonScript Development Platform

## Canonical CI Entry Point Specification v1.0

**Status:** VALIDATED
**Target Release:** ReasonScript Development Platform v0.5
**Specification ID:** `reasonscript-ci-entry/1.0`

## 1. Purpose

This specification defines the canonical entry point for all development validation within the ReasonScript Development Platform.

Beginning with ReasonScript Development Platform v0.5, the command

```text
reason ci
```

is the official entry point for repository validation.

Individual CLI commands remain available but are considered implementation-level commands rather than the primary developer workflow.

## 2. Goals

The canonical entry point provides:

- a single deterministic validation command
- a stable interface for Coding Agents
- a stable interface for CI
- a stable interface for local development
- reproducible validation
- simplified project operation

## 3. Design Principles

The canonical entry point shall be:

- deterministic
- specification-driven
- reproducible
- implementation-independent
- extensible

New validation stages shall be added through the CI pipeline without changing the developer entry point.

## 4. Canonical Entry Point

The official validation command is

```text
reason ci
```

Optional arguments:

```text
reason ci --json
reason ci --out <directory>
reason ci --skip-tests
```

Future options may be added while preserving backward compatibility.

## 5. Canonical Workflow

The command executes the complete platform validation workflow.

```text
Checkout Repository
↓
Environment Setup
↓
Workspace Validation
↓
Diagnostics Validation
↓
Artifact Validation
↓
Golden Tests
↓
Agent Protocol Validation
↓
Compatibility Verification
↓
Unit / Integration Tests
↓
Completion Report
```

The execution order is fixed.

## 6. Required Validation Contracts

The canonical workflow validates:

- Workspace Foundation
- Diagnostics Freeze
- Artifact Schema Freeze
- Golden Test Corpus
- Agent Development Protocol
- CI Stabilization

Future platform contracts shall be integrated into this workflow.

## 7. Exit Status

The command shall return `PASS` when every validation phase succeeds.

The command shall return `FAIL` when any required validation phase fails.

The pipeline follows fail-fast semantics.

## 8. Machine-Readable Outputs

The command generates

```text
ci_report.json
ci_summary.json
```

These reports shall conform to `reasonscript-ci/1.0`.

## 9. Relationship to Individual Commands

The following commands remain supported:

```text
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

These commands are implementation-level interfaces.

Normal development, Coding Agent execution, and CI workflows shall invoke `reason ci` as the primary entry point.

## 10. Coding Agent Policy

Coding Agents shall execute `reason ci` before reporting task completion.

Execution of individual commands is permitted for diagnosis, debugging, or incremental development but does not replace the canonical validation workflow.

## 11. CI Policy

GitHub Actions and equivalent CI systems shall invoke `reason ci` as the primary validation command.

Platform-specific scripts shall not duplicate the validation pipeline unless required for infrastructure reasons.

## 12. Local Development Policy

Developers are encouraged to use `reason ci` before committing changes.

Individual commands remain available for focused investigation and debugging.

## 13. Backward Compatibility

Existing CLI commands remain stable.

Introducing new validation stages shall not require changing the canonical entry point.

The following invariant shall be preserved: `reason ci` shall remain the single official validation command throughout the v0.5 lifecycle.

## 14. Determinism

The canonical entry point guarantees:

- deterministic execution order
- deterministic validation
- deterministic artifact generation
- deterministic diagnostics
- deterministic reporting

## 15. Validation Rules

Entry Point Validation:

```text
CE-001 Missing CI pipeline
CE-002 Invalid execution order
CE-003 Required validation omitted
CE-004 Report generation failure
CE-005 Pipeline termination failure
```

## 16. Compatibility

Compatible with:

- `reasonscript-workspace/1.0`
- `reasonscript-diagnostics/1.0`
- `reasonscript-artifacts/1.0`
- `reasonscript-golden-tests/1.0`
- `reasonscript-agent-protocol/1.0`
- `reasonscript-ci/1.0`
- `reasonscript-cli/0.5`

## 17. Out of Scope

This specification excludes:

- deployment workflows
- release automation
- package publishing
- IDE launch procedures
- Frontend SDK execution
- runtime performance benchmarking

## 18. Completion Criteria

This specification is considered implemented when:

- `reason ci` is the documented canonical entry point.
- Coding Agents use `reason ci` as the final validation command.
- CI pipelines invoke `reason ci`.
- Machine-readable reports are generated.
- Individual CLI commands remain available as lower-level interfaces.
- Repository documentation consistently identifies `reason ci` as the standard validation entry point.
