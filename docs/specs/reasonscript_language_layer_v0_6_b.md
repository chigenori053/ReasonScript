# ReasonScript Language Layer v0.6-B Specification

Specification ID: reasonscript-language-layer/0.6-B
Title: module/model Equivalence Validation and CI/CD Consistency Revalidation
Status: VALIDATED locally
Base Specification: reasonscript-language-layer/0.6
Milestone: LL-001B

## Purpose

ReasonScript v0.6-B accepts both `module Example { ... }` and
`model Example { ... }` as top-level Human Surface constructs.

This milestone guarantees that:

- `module` and `model` are distinguishable at L0/L1.
- Surface AST preserves the original spelling in `source_kind`.
- Equivalent `module` and `model` programs lower to identical L3 Reason IR.
- L4 ExecutionPlan, L5 Semantic Simulation, and L6 Knowledge Evidence are identical.
- Playground artifacts include `diagnostics.json`.
- CI executes the compatibility and artifact contract tests that cover these rules.

## Layer Requirements

L0 Human Surface:

- `module` remains valid compatibility syntax.
- `model` is accepted as the preferred Human Surface alias for reasoning model definitions.

L1 Surface AST:

- `source_kind` is required in `ModuleNode`.
- Allowed values are `module` and `model`.
- `module Example` and `model Example` must produce different Surface AST artifacts.

L2 Semantic AST:

- Semantic validation, name resolution, and type validation must be identical for equivalent bodies.
- Diagnostics may differ only by source location or source spelling metadata.

L3-L6 Reasoning Core:

- `source_kind` must not appear as a semantic discriminator.
- Reason IR, ExecutionPlan, SimulationResult, and Knowledge artifacts require strict equality for equivalent programs.

L7 Developer Projection:

- Projection may display `source_kind`.
- Projection must not imply different reasoning semantics.
- Diagnostics View consumes `diagnostics.json` as an official pipeline artifact.

## Artifact Contract

v0.6-B official artifacts:

```text
source.rsn
surface_ast.json
semantic_ast.json
reason_ir.json
execution_plan.json
simulation.json
knowledge.json
diagnostics.json
```

## Required Validation

The repository validates this milestone with:

```text
tests/compatibility/test_module_model_equivalence.py
tests/playground/test_artifact_contract_v0_6.py
tests/ci/test_ci_stabilization.py
```

CI may run the required files directly, or run the consolidated groups:

```bash
python3 scripts/test_platform.py test
python3 scripts/test_platform.py regression
```

The consolidated test target includes:

- `tests/compatibility`
- `language_surface_ast_mapping_tests`
- `tests/playground`

## Acceptance Criteria

- `model Example { ... }` is accepted.
- `module Example { ... }` remains accepted.
- Surface AST preserves `source_kind`.
- Surface AST differs only by `source_kind` for equivalent module/model programs.
- Reason IR is identical.
- ExecutionPlan is identical.
- Simulation is identical.
- Knowledge is identical.
- `diagnostics.json` is included in Playground artifact export.
- CI runs the v0.6-B equivalence and artifact contract tests.
- No L3-L6 semantic behavior changes are introduced by `source_kind`.

## Final Definition

module and model are different Human Surface spellings.

Surface AST preserves that spelling through `source_kind`.

Reason IR is canonical and must not change because of `source_kind`.

ExecutionPlan, Semantic Simulation, and Knowledge Evidence must remain identical
for semantically equivalent module/model programs.

CI/CD must continuously validate this equivalence.

This confirms the central Language Layer rule:

```text
L0/L1 may preserve authoring form.
L3-L6 must preserve semantic canonicality.
```
