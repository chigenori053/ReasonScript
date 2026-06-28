# ReasonScript Language Layer v0.6-C Specification

Specification ID: reasonscript-language-layer/0.6-C
Title: model Preferred Syntax Projection
Status: IMPLEMENTED locally
Base Specification: reasonscript-language-layer/0.6
Previous Milestone: LL-001B - module/model Equivalence and CI/CD Revalidation
Milestone: LL-001C

## Purpose

ReasonScript v0.6-C presents `model` as the preferred Human Surface syntax and
keeps `module` as compatibility syntax.

This milestone only changes L7 Developer Projection:

- `source_kind` may affect Developer Projection wording.
- `source_kind` must not affect Reason IR.
- `source_kind` must not affect ExecutionPlan.
- `source_kind` must not affect Semantic Simulation.
- `source_kind` must not affect Knowledge Evidence.

## Summary View

The Playground Summary View displays:

- Source Kind
- Syntax Status
- Construct Type
- Normalized Core
- Core Semantics

For `model Example`, projection reports preferred syntax and
`ReasonGraph(namespace="Example")`.

For `module Example`, projection reports compatibility syntax and
`ReasonGraph(namespace="Example")`.

Both forms are presented as semantically identical at core layers for v0.6-C.

## Diagnostics View

The Diagnostics View consumes `diagnostics.json`.

When no diagnostics exist, it renders `No diagnostics.`.

When `module` compatibility context is emitted, it is informational only:

```text
severity: info
layer: L7
code: LL-001C-MODULE-COMPAT-INFO
```

It must not block compilation or execution.

## Projection Artifact

The optional `projection_summary.json` artifact is derived from existing
Surface AST and Reason IR artifacts. It is explanatory only and must not be
used as a source of truth for core semantics.

## Required Validation

The repository validates this milestone with:

```text
tests/playground/test_projection_summary_v0_6.py
tests/playground/test_diagnostics_view_v0_6.py
tests/compatibility/test_projection_core_non_regression.py
```

Recommended CI scope:

```bash
python3 -m pytest tests/compatibility language_surface_ast_mapping_tests tests/playground
```
