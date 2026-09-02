# ReasonScript Development Environment Phase 7.6

## CI Stabilization Specification v1.0

**Status:** DRAFT
**Target Release:** ReasonScript Development Platform v0.5
**Specification ID:** `reasonscript-ci/1.0`

## 1. Purpose

This specification defines the canonical Continuous Integration (CI) workflow for the ReasonScript Development Platform.

The CI Stabilization phase standardizes automated validation, artifact verification, regression testing, and protocol compliance to ensure every repository change satisfies the platform contracts before integration.

This specification applies to:

- GitHub Actions
- Local validation workflows
- Coding Agents
- CLI automation

## 2. Goals

The CI system shall provide:

- deterministic validation
- automatic regression detection
- protocol enforcement
- artifact verification
- compatibility verification
- reproducible execution

## 3. Design Principles

The CI workflow shall be:

- deterministic
- reproducible
- platform-independent
- validation-first
- specification-driven
- machine-readable

Every CI execution shall produce identical results for identical repository contents.

## 4. Canonical CI Workflow

Every CI execution shall perform the following sequence.

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
Unit / Integration Tests
↓
Completion Report
```

Every phase shall complete successfully before the next phase begins.

## 5. Required Commands

The CI workflow shall execute at minimum:

```text
reason workspace
reason check
reason analyze
reason artifacts
reason validate-artifacts
reason golden
reason agent-protocol
```

Optional commands:

```text
reason summary
reason manifest
reason index
reason export
reason agent-report
```

`reason ci` implements the canonical pipeline described in Section 4 and orchestrates the required commands above.

The repository-wide test definition is `python3 scripts/test_platform.py test`.
Both `reason ci` and the GitHub Actions Test workflow shall invoke this same
definition. The test target includes unit, integration, regression,
compatibility, golden, playground, CLI, and native Rust tests, and shall not
run a nested test directory more than once.

## 6. Validation Pipeline

The CI pipeline shall validate:

- Workspace Foundation
- Diagnostics
- Artifact Schema
- Golden Test Corpus
- Agent Development Protocol

Every validation failure shall terminate the pipeline.

## 7. Test Categories

The CI workflow shall execute:

- Unit Tests
- Integration Tests
- Compatibility Tests
- Golden Tests
- CLI Tests

Additional test categories may be added without modifying this specification.

Continuous tests shall protect current product behavior or a supported
compatibility contract. Tests whose only purpose is to prove that a completed
historical phase document or changelog entry exists shall not remain in the
repository-wide suite. Identical checks shall have one canonical owner.

## 8. Artifact Verification

CI shall verify:

- `artifact_manifest.json`
- `artifact_summary.json`
- `diagnostics.json`
- `diagnostics_summary.json`

Every artifact shall conform to `reasonscript-artifacts/1.0`.

## 9. Golden Verification

CI shall verify:

- Golden manifest
- Golden summaries
- Expected diagnostics
- Expected artifacts
- Runtime outputs

Golden failures shall fail the pipeline.

## 10. Agent Protocol Verification

CI shall execute:

```text
reason agent-protocol --json
```

The protocol validator shall report `AP-001` through `AP-010`. No protocol violations shall be permitted.

## 11. Compatibility Verification

CI shall verify compatibility with:

- Workspace
- Diagnostics
- Artifact Schema
- Language Surface
- Reason IR
- Execution Plan
- Simulation
- Knowledge

## 12. Failure Policy

If any validation fails:

- terminate execution
- preserve generated artifacts
- preserve diagnostics
- report the failing phase

Subsequent validation stages shall not execute.

## 13. Machine-Readable Reports

CI shall generate:

```text
ci_report.json
ci_summary.json
```

Example:

```json
{
  "version": "1.0",
  "status": "PASS",
  "workspace": true,
  "diagnostics": true,
  "artifacts": true,
  "golden": true,
  "agent_protocol": true,
  "tests": 39
}
```

## 14. Determinism

The CI workflow guarantees:

- deterministic command execution
- deterministic artifact generation
- deterministic diagnostics
- deterministic reporting

## 15. Validation Rules

CI Validation:

```text
CI-001 Missing workflow
CI-002 Required command failed
CI-003 Workspace validation failed
CI-004 Diagnostics validation failed
CI-005 Artifact validation failed
CI-006 Golden test failed
CI-007 Agent protocol violation
CI-008 Test failure
CI-009 Compatibility failure
CI-010 Report generation failure
```

## 16. GitHub Actions Requirements

The canonical workflow shall:

- execute on push
- execute on pull request
- fail on validation errors
- upload generated artifacts when configured
- publish machine-readable reports
- use `scripts/test_platform.py test` as the single repository-wide test definition
- avoid repeating regression or canonical CI execution inside the Test workflow

The workflow shall remain deterministic across supported operating systems.

## 17. Repository Requirements

The repository shall include:

```text
.github/workflows/
tests/
golden/
AGENTS.md
docs/specifications/
docs/changelog/
```

## 18. Compatibility

Compatible with:

- `reasonscript-workspace/1.0`
- `reasonscript-diagnostics/1.0`
- `reasonscript-artifacts/1.0`
- `reasonscript-golden-tests/1.0`
- `reasonscript-agent-protocol/1.0`
- `reasonscript-cli/0.5`

## 19. Out of Scope

This specification excludes:

- Deployment pipelines
- Release automation
- Performance benchmarking
- Security scanning
- Dependency update automation
- Multi-repository orchestration
- IDE integration
- Frontend SDK

## 20. Completion Criteria

Phase 7.6 is complete when:

- The canonical CI workflow is implemented.
- All required CLI commands execute successfully in CI.
- Workspace, Diagnostics, Artifact Schema, Golden Test Corpus, and Agent Protocol validations are integrated into the CI pipeline.
- Validation rules `CI-001` through `CI-010` are implemented.
- `ci_report.json` and `ci_summary.json` are generated.
- CI execution is deterministic and reproducible.
- Regression tests confirm stable CI behavior.
- Repository changes are automatically rejected when platform contracts are violated.
