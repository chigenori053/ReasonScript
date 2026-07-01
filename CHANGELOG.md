# Changelog

## ReasonScript IDE Phase 3.5 - Standard IDE Layout Simplification - 2026-07-01

### Status

VALIDATED

### Summary

ReasonScript IDE Phase 3.5 has been completed as the Standard IDE Layout
Simplification phase.

This phase reorganizes the Playground-first IDE into a simpler Android
Studio-style layout with five major regions: Top Bar, Left Project Pane, Center
Editor, Right Inspector, and Bottom Tool Window.

The overloaded right-pane tab structure has been reduced to five primary tabs:
Overview, Plan, Simulation, Knowledge, and Artifacts. Operational feedback has
been moved into a Bottom Tool Window with Problems, Output, Logs, and Tests
tabs.

### Added

- Added Standard IDE Layout v0.2 implementation.
- Added Top Bar with Project, File, Mode, Validate, Run, Analyze, Audit, and
  Status.
- Added simplified Right Inspector tabs:
  - Overview
  - Plan
  - Simulation
  - Knowledge
  - Artifacts
- Added Bottom Tool Window tabs:
  - Problems
  - Output
  - Logs
  - Tests
- Added `StandardLayoutViews.tsx`.
- Added Phase 3.5 layout contract tests.
- Added Phase 3.5 development documentation:
  - `standard_ide_layout.md`
  - bottom tool window contract
  - cross-platform UI readiness
  - layout migration map

### Changed

- Consolidated Pipeline and Summary into Overview.
- Moved detailed diagnostics to Bottom Problems.
- Moved runtime output to Bottom Output.
- Moved AST, Semantic AST, Reason IR, Validation, and Raw JSON into Artifacts.
- Moved ExecutionPlan into Plan.
- Moved Simulation, Runtime, Input, and Trace information into Simulation.
- Moved Knowledge and evidence information into Knowledge.
- Reclassified Diff, Regression, Baseline, and related outputs toward Bottom
  Tests or future Audit sections.
- Preserved existing functionality through relocation, grouping, and collapsible
  detail sections.

### Cross-platform Readiness

- The five-region layout is compatible with browser and future desktop shell
  embedding.
- UI logic does not depend on OS-specific path separators.
- `relative_path` values are treated as slash-normalized display paths.
- Keyboard shortcuts remain command-oriented for future desktop menu bindings.
- Right Inspector and Bottom Tool Window are compatible with future resizable
  panes.
- Native menus, native file dialogs, packaging, and installers remain outside
  Phase 3.5.

### Validation

- `python3 scripts/dev.py test ide`
  - 104 passed
- `python3 -m pytest tests/ide/test_standard_layout_contract.py -v --tb=short`
  - 4 passed
- `npm run build` in `apps/reasonscript-ide/ui`
  - passed

### Compatibility

- Parser behavior is unchanged.
- Runtime behavior is unchanged.
- Reason IR semantics are unchanged.
- ExecutionPlan semantics are unchanged.
- Simulation semantics are unchanged.
- Knowledge semantics are unchanged.
- `/api/analyze` contract is unchanged.
- Workspace list/read/save contracts are unchanged.
- Phase 3 workspace editing behavior is unchanged.
- Phase 3.5 changes are UI layout and information architecture changes only.

---

## ReasonScript IDE Phase 3 - Local Workspace Editing Foundation - 2026-07-01

### Status

VALIDATED

### Summary

ReasonScript IDE Phase 3 defines the Local Workspace Editing Foundation.

This phase extends the Playground-first IDE from temporary source editing
to workspace file-based development. It introduces selected file state,
editor binding, dirty state tracking, save workflow, analyze-current-file
workflow, per-file diagnostics, and per-file artifact identity. Runtime and
compiler semantics are unchanged — Phase 3 only changes how source text
reaches `/api/analyze`.

### Scope

- Workspace file selection
- Source editor binding
- File read / save
- Dirty state tracking
- Analyze selected file
- Per-file analyze result binding
- Per-file diagnostics
- Per-file artifact identity
- Missing file handling
- Path traversal protection
- Workspace editing documentation
- Workspace editing contract tests

### Non-Goals

- Desktop IDE full implementation
- Terminal emulator
- Full LSP integration
- Multi-file semantic linking
- Package manager
- Git integration
- Advanced runtime replay
- Cloud workspace

### Added

- Added `playground/backend/workspace.py`: workspace scan, read, save, and
  path-safety helpers.
- Added `POST /api/workspace/list` (also serves workspace refresh).
- Added `POST /api/workspace/read`.
- Added `POST /api/workspace/save`.
- Added optional `source_context` field to the `/api/analyze` request
  (`workspace_root`, `relative_path`, `dirty`) — omitting it preserves the
  exact Phase 2 behavior.
- Added `source_context` (with a deterministic `artifact_id`) to the
  `/api/analyze` response when a workspace file was analyzed.
- Added `relative_path` stamping on diagnostics when `source_context` is
  present.
- Added best-effort per-file artifact persistence under
  `<workspace_root>/.reasonscript/artifacts/<artifact_id>/`, reusing the
  existing Phase 2 artifact file names.
- Added `WorkspaceExplorer` sidebar to the Playground frontend: open a
  workspace root, browse the file tree, select a `.rsn`/`.reason` file.
- Added file-aware Source Editor: selected-file header (filename, dirty
  indicator, read-only/missing/stale badges), Save action, and a
  file-bound Analyze action.
- Added per-file analyze result cache in the frontend so switching files
  restores that file's last analyze result.
- Added Phase 3 development documentation:
  `workspace_editing_foundation.md`, `file_operation_contract.md`,
  `editor_state_contract.md`, `per_file_artifact_contract.md`,
  `per_file_diagnostics_contract.md`.
- Added workspace contract tests under `tests/ide/`.

### Required File Operations

- `list_workspace_files` — `POST /api/workspace/list`
- `read_workspace_file` — `POST /api/workspace/read`
- `save_workspace_file` — `POST /api/workspace/save`
- `refresh_workspace` — re-invoke `POST /api/workspace/list`
- `select_workspace_file` — frontend-only state; no backend endpoint (the
  backend is stateless per-request)

### Source File Extensions

- `.rsn` as preferred ReasonScript source extension
- `.reason` as optional compatibility extension

### Analyze Request Extension

`POST /api/analyze` may include optional `source_context`:

```json
{
  "source": "model Test {}",
  "compiler_mode": "default",
  "source_context": {
    "workspace_root": "/path/to/project",
    "relative_path": "examples/test.rsn",
    "dirty": false
  }
}
```

### Artifact Identity

Per-file artifacts use a deterministic source-path hash:

```
.reasonscript/artifacts/<artifact_id>/
```

where `artifact_id = sha256(relative_path)[:16]`. Required artifact names
remain unchanged: `ast.json`, `semantic_ast.json`, `reason_ir.json`,
`execution_plan.json`, `simulation.json`, `knowledge.json`,
`diagnostics.json`, `validation.json`.

### Acceptance Criteria

- Workspace file tree can select ReasonScript source files.
- Selected file content loads into Source Editor.
- Dirty state is tracked.
- Selected file can be saved.
- Path traversal is rejected.
- Selected file can be analyzed through `/api/analyze`.
- Analyze result is bound to selected file.
- Runtime panels display selected file analyze result.
- Diagnostics are associated with selected file.
- Missing selected file does not crash the IDE.
- Artifact identity is deterministic per file.
- Temporary source analyze mode remains supported.

### Validation

```
python3 scripts/dev.py test ide
python3 scripts/dev.py test backend
python3 scripts/dev.py test smoke
npm run build (playground/frontend)
```

### Compatibility

- Parser behavior is unchanged.
- Runtime behavior is unchanged.
- Reason IR semantics are unchanged.
- ExecutionPlan semantics are unchanged.
- Simulation semantics are unchanged.
- Knowledge semantics are unchanged.
- `/api/analyze` remains backward compatible with the Phase 2 request
  shape.
- `source_context` is optional.
- Temporary source analyze mode remains supported.

---

## ReasonScript IDE Phase 2 - Playground-first IDE Runtime Integration - 2026-06-29

### Status

VALIDATED

### Summary

ReasonScript IDE Phase 2 has been completed as the official
Playground-first Runtime Integration layer.

The Playground IDE now treats `POST /api/analyze` as the primary contract
endpoint for Source -> Surface AST -> Semantic AST -> Reason IR ->
ExecutionPlan -> Simulation -> Knowledge -> Diagnostics inspection.

The analyze response now returns a deterministic payload containing pipeline
status, runtime artifacts, structured view data, diagnostics, and compiler
mode.

### Added

- Added stabilized `/api/analyze` response contract.
- Added fixed pipeline stage ids:
  - `source`
  - `surface_ast`
  - `semantic_ast`
  - `reason_ir`
  - `execution_plan`
  - `simulation`
  - `knowledge`
  - `diagnostics`
- Added fixed stage status values:
  - `success`
  - `warning`
  - `error`
  - `skipped`
  - `unavailable`
- Added artifact state handling.
- Added diagnostics-to-pipeline stage mapping.
- Added Pipeline Overview tab to the Playground frontend.
- Added shared analyze result state for runtime artifact display.
- Added structured display integration for ExecutionPlan, Simulation,
  Knowledge, Diagnostics, and Runtime IO.
- Added Desktop-compatible ViewModel status updates.
- Added Phase 2 development documentation.
- Added `/api/analyze` contract test.

### Fixed

- Stabilized missing artifact handling.
- Ensured missing artifacts render as empty, skipped, or unavailable states.
- Prevented missing artifacts from crashing the IDE.
- Normalized diagnostic severity to `error`, `warning`, or `info`.
- Classified unknown diagnostics under the `diagnostics` stage.

### Analyze API Contract

`POST /api/analyze` accepts:

```json
{
  "source": "module Test { calculation Value { result = 42 } }",
  "compiler_mode": "default"
}
```

The response contains:

```json
{
  "ok": true,
  "compiler_mode": "default",
  "pipeline": {
    "stages": []
  },
  "artifacts": {},
  "views": {},
  "diagnostics": []
}
```

Required pipeline stages:

- `source`
- `surface_ast`
- `semantic_ast`
- `reason_ir`
- `execution_plan`
- `simulation`
- `knowledge`
- `diagnostics`

Required artifact names:

- `ast.json`
- `semantic_ast.json`
- `reason_ir.json`
- `execution_plan.json`
- `simulation.json`
- `knowledge.json`
- `diagnostics.json`
- `validation.json`

Every diagnostic returned by `/api/analyze` includes `code`, `message`,
`severity`, `stage`, and `source_range`. Unknown diagnostics are classified
under the `diagnostics` stage.

### Validation

- `python3 scripts/dev.py test smoke`
- `python3 scripts/dev.py test backend`
- `python3 scripts/dev.py test ide`
- `npm run build` in `playground/frontend`
- `npm run build` in `apps/reasonscript-ide/ui`

All validation commands passed.

### Compatibility

- Parser behavior is unchanged.
- Runtime behavior is unchanged.
- Reason IR semantics are unchanged.
- ExecutionPlan semantics are unchanged.
- Simulation semantics are unchanged.
- Knowledge semantics are unchanged.
- Phase 2 only stabilizes Playground IDE runtime integration.

### Positioning

```text
Phase 1:
  Development Environment
  Status: VALIDATED

Phase 2:
  Playground-first IDE Runtime Integration
  Status: VALIDATED

Next:
  Phase 3 candidate selection
```

## ReasonScript Language Layer v0.6-D - 2026-06-29

### Added

- Added Human Surface top-level construct policy.
- Defined `model` as active preferred syntax.
- Defined `module` as active compatibility syntax.
- Reserved `world` for WorldModel / simulation-domain syntax.
- Reserved `system` for multi-model orchestration syntax.
- Reserved `component` for UI / SDK structural composition syntax.
- Added reserved top-level construct diagnostic policy.

### Fixed

- Clarified that reserved top-level constructs must not silently parse as `model` or `module`.
- Clarified that `source_kind` remains L1/L7 metadata unless a future specification defines distinct core semantics.
- Preserved module/model L3-L6 equivalence guarantees from v0.6-B.

### Validation

- model active preferred syntax policy verified.
- module active compatibility syntax policy verified.
- reserved construct diagnostics verified.
- module/model core non-regression verified.
- top-level construct projection policy verified.
- Playground frontend build verified.

## ReasonScript Language Layer v0.6-C - 2026-06-29

### Added

- Added L7 Developer Projection support for `source_kind`.
- Added Playground Summary View presentation for `model` and `module`.
- Displayed `model` as preferred Human Surface syntax.
- Displayed `module` as compatibility syntax.
- Displayed normalized ReasonGraph target for top-level constructs.
- Added Diagnostics View support for `diagnostics.json`.

### Fixed

- Clarified that source spelling differences are projection metadata, not Reason IR semantics.
- Prevented Developer Projection from implying different core semantics for `module` and `model`.

### Validation

- Source kind projection verified.
- model preferred syntax projection verified.
- module compatibility syntax projection verified.
- Diagnostics artifact consumption verified.
- L3-L6 non-regression verified.
- Playground frontend build verified.

## ReasonScript Language Layer v0.6-B - 2026-06-28

### Added

- Accepted `model Example { ... }` as a top-level Human Surface alias.
- Added `source_kind` to Surface AST to preserve original top-level spelling.
- Added module/model equivalence validation across Reason IR, ExecutionPlan,
  Simulation, and Knowledge.
- Added `diagnostics.json` to Playground pipeline artifact export.

### Fixed

- Clarified that Human Surface spelling must not affect Reason IR semantics.
- Strengthened CI/CD coverage for Language Layer artifact consistency.

### Validation

- Surface AST source_kind distinction verified.
- Reason IR equivalence verified.
- ExecutionPlan equivalence verified.
- Simulation and Knowledge equivalence verified.
- Playground artifact contract verified.

## reasonscript-language-surface/0.5 - 2026-06-28

ReasonScript Language Surface v0.5 feature freeze.

### Frozen Surface

- Module system, declarations, type system, expressions, and statements
- Literal, enum, optional, struct, nested struct, guard, OR, and range patterns
- Source -> Surface AST -> Semantic AST -> Reason IR -> ExecutionPlan ->
  Simulation -> Knowledge pipeline
- Pattern Identity, canonical path generation, and branch evidence propagation

### Fixed Interfaces

- `reasonscript-language-surface/0.5`
- `parser/0.5`
- `reasonscript-ast/0.5`
- `reason-ir/0.5`
- `execution-plan/0.5`

### Compatibility Policy

- `0.5.x` releases may include bug fixes, diagnostics, compiler optimizations,
  and performance improvements.
- Syntax, semantic meaning, IR schema, canonical path generation, and Pattern
  Identity are frozen for the v0.5 line.
- New language features are deferred to v0.6.

## reasonscript-semantic-language/0.2 - 2026-06-15

ReasonScript Semantic Language v0.2 Core freeze.

### Frozen Core

- SemanticUnit and the seven adopted SemanticUnit types
- SemanticRelation and the eight core relation types
- SCV-1 structural validation
- Reasoning Space and SemanticPlan
- deterministic SemanticSimulation and SimulationResult
- validated Knowledge emergence with complete evidence

### Guarantees

- deterministic reasoning for identical graph, plan, and constraints
- SCV-1 enforcement throughout the reasoning pipeline
- immutable Reasoning Space during simulation
- trace, evidence, and confidence preservation
- reproducible SimulationResult and Knowledge JSON

### Out of Scope

- SCV-2 through SCV-5
- Knowledge repositories, persistence, retrieval, and re-reasoning
- MemorySpace, WorldModel, natural language parsing, and external execution

## reasonscript-language-surface/0.1 - 2026-06-14

ReasonScript Language Surface v0.1 release.

### Released

- Deterministic Source -> Surface AST -> Semantic AST -> Reason IR ->
  ExecutionPlan pipeline
- Module namespaces, imports, aliases, visibility, and qualified names
- Declarations, relations, expressions, patterns, statements, and Calculations
- Primitive and Reason State type annotations as validation contracts
- Canonical `node_type` serialization and round-trip compatibility
- Fixed AST, expression, pattern, statement, Calculation, type, and namespace
  validation families

### Fixed Interfaces

- `reasonscript-language-surface/0.1`
- `reasonscript-ast/0.1`
- `parser/0.1`
- `compiler/0.1`
- `reason-ir/0.1`
- `execution-plan/0.1`
- `reasonscript-calculation-semantics/0.1`

## 0.1.0-alpha - 2026-06-13

First integrated ReasonScript Platform alpha release.

### Added

- State-first layered Hybrid Runtime and transaction model
- Versioned `reason-ir/0.1` JSON ABI
- Common DTO declarations for Rust, Python, TypeScript, Go, and Java
- Five-layer platform conformance framework
- Versioned `reasonscript-ast/0.1` semantic AST ABI
- Deterministic `parser/0.1` Source-to-AST contract
- Deterministic `compiler/0.1` AST-to-Reason-IR contract
- End-to-end Source -> AST -> Reason IR -> Runtime validation

### Fixed Interfaces

- `reason-ir/0.1`
- `reasonscript-ast/0.1`
- `parser/0.1`
- `compiler/0.1`
- `transaction/0.1`
- `common-dto/0.1`
- `conformance-framework/0.1`

### Known Limitations

- The user-facing syntax remains experimental.
- Macros, language server, formatter, optimizer, distributed Runtime,
  persistence, and event sourcing are not included.
- Go conformance was not executed in the release environment because the Go
  toolchain was unavailable.
- Java DTO declarations compile, but a Java JSON codec adapter is not included.
- Full five-language SDK compatibility certification is not granted.
