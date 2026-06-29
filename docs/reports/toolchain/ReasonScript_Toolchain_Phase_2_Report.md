# ReasonScript Toolchain Phase 2 Report

Version: `reasonscript-toolchain/0.2`

Status: Complete

## Implemented Scope

Phase 2 extends the single-package toolchain with a deterministic workspace and
package graph model.

Implemented components:

- `reason.workspace.toml` parsing
- Workspace discovery from nested package paths
- Package manifest dependency parsing
- Workspace-local path dependencies
- Exact-version dependency validation
- Package graph serialization with `reasonscript-package-graph/0.1`
- Deterministic topological build ordering
- Duplicate package, missing package, unknown dependency, invalid version, and
  dependency cycle detection
- `PlatformDiagnostic` conversion for dependency failures
- Workspace-aware `reason build`, `reason check`, `reason test`, and `reason run`
- `--package` selection for workspace commands
- Dependency-aware build cache invalidation for downstream packages
- LSP package graph loading
- IDE workspace root detection and workspace command execution

## Conformance

Added `toolchain_phase2_tests` covering:

- TC2-001 Workspace Discovery
- TC2-002 Workspace Manifest Parse
- TC2-003 Package Manifest Parse
- TC2-004 Local Dependency Resolution
- TC2-005 Dependency Graph Creation
- TC2-006 Topological Sort
- TC2-007 Dependency Cycle Detection
- TC2-008 Missing Package Detection
- TC2-009 Unknown Dependency Detection
- TC2-010 Exact Version Validation
- TC2-011 Workspace Build
- TC2-012 Package Build
- TC2-013 Workspace Check
- TC2-014 Workspace Test
- TC2-015 Workspace Run
- TC2-016 Default Package Resolution
- TC2-017 Incremental Build
- TC2-018 PlatformDiagnostic Integration
- TC2-019 LSP Package Graph Integration
- TC2-020 IDE Workspace Integration

## Validation

Targeted validation:

```text
python3 -m pytest toolchain_phase1_tests toolchain_phase2_tests lsp_phase1_tests ide_phase1_tests
99 passed
```

Full repository validation:

```text
python3 -m pytest --import-mode=importlib
606 passed, 2 skipped
```

The repository still has pre-existing duplicate test module basenames that can
interrupt default pytest collection; `--import-mode=importlib` runs the full
suite successfully.
