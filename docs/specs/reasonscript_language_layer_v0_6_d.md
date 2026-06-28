# ReasonScript Language Layer v0.6-D Specification

Specification ID: reasonscript-language-layer/0.6-D
Title: Human Surface Top-Level Construct Policy
Status: IMPLEMENTED locally
Base Specification: reasonscript-language-layer/0.6
Previous Milestones: LL-001B, LL-001C
Milestone: LL-002

## Purpose

ReasonScript v0.6-D defines the official top-level Human Surface construct
policy before future constructs are activated.

Current construct categories:

- `model`: active preferred syntax.
- `module`: active compatibility syntax.
- `world`: reserved for WorldModel / simulation-domain syntax.
- `system`: reserved for multi-model orchestration syntax.
- `component`: reserved for UI / SDK structural composition syntax.

## Active Constructs

`model Example { ... }` is accepted and preserved as
`source_kind = "model"` in Surface AST. L7 projection marks it as preferred
syntax and as a Reasoning Model.

`module Example { ... }` remains accepted for backward compatibility and is
preserved as `source_kind = "module"` in Surface AST. L7 projection marks it as
compatibility syntax and states that core semantics are identical to `model` for
v0.6-D.

Both forms lower to identical Reason IR, ExecutionPlan, Simulation, and
Knowledge artifacts for equivalent bodies.

## Reserved Constructs

`world`, `system`, and `component` are reserved but not active syntax in v0.6-D.

Reserved constructs are rejected by default with:

```text
code: LL-002-RESERVED-TOP-LEVEL-CONSTRUCT
layer: L1
severity: error
```

Reserved constructs must not silently parse as `model` or `module`, must not
emit reserved `source_kind` values in ordinary Surface AST output, and must not
lower into Reason IR without an explicit future specification or experimental
activation.

## Projection Policy

L7 projection presents active and compatibility constructs clearly:

- `model`: preferred Human Surface syntax, canonical ReasonScript reasoning model.
- `module`: compatibility syntax, identical to `model` for v0.6-D.

Reserved constructs do not project as active constructs. If encountered, they
are represented through diagnostics only.

## Artifact Contract

The v0.6-B/C artifact contract remains unchanged:

```text
source.rsn
surface_ast.json
semantic_ast.json
reason_ir.json
execution_plan.json
simulation.json
knowledge.json
diagnostics.json
projection_summary.json
```

`diagnostics.json` is required for Playground artifacts. `projection_summary.json`
is optional L7 projection metadata and is not a source of truth for core
semantics.

## Required Validation

The repository validates this milestone with:

```text
tests/compatibility/test_top_level_construct_policy_v0_6.py
tests/playground/test_top_level_construct_projection_v0_6.py
tests/playground/test_reserved_construct_diagnostics_v0_6.py
```

Recommended CI scope:

```bash
python3 -m pytest tests/compatibility tests/playground language_surface_ast_mapping_tests tests/ci/test_ci_stabilization.py
```

Frontend validation:

```bash
cd playground/frontend && npm run build
```
