# ReasonScript Language Surface v0.5 Release Notes

Release: `reasonscript-language-surface/0.5`

Status: Feature Freeze Draft

## Summary

Language Surface v0.5 freezes the first feature-complete ReasonScript language
surface. The release stabilizes syntax, semantic lowering, pattern identity,
canonical branch paths, and the Source -> Knowledge pipeline.

## Frozen Feature Set

- Module, package, import, export, and visibility syntax.
- Function, calculation, struct, enum, const, and let declarations.
- Primitive, struct, enum, optional, and runtime-facing types.
- Calls, comparisons, runtime calls, and calculation expressions.
- Return, if, match, and loop-family statements.
- Literal, enum, optional, struct, nested struct, guard, OR, and range patterns.

## Frozen Semantic Contracts

- `pattern_identity` is emitted for selected match patterns.
- Canonical path generation is deterministic.
- ExecutionPlan, Simulation, and Knowledge preserve identical selected branch evidence.
- OR patterns expose only the selected alternative downstream.
- Range patterns emit deterministic range metadata, `RangeEvaluation`, and Knowledge `range_evidence`.

## Compatibility

The v0.5 line accepts bug fixes, diagnostics, compiler optimizations, and
performance work only when they preserve syntax, semantic meaning, IR shape,
canonical path generation, and Pattern Identity.

New language features are deferred to v0.6.

## Validation

The release validation suite is represented by:

- `tests/compatibility/test_language_surface_v0_5.py`
- `playground_language_surface_v0_5_matrix.json`
- `playground_language_surface_v0_5_audit.md`

The suite covers parser, AST, validation, pattern families, Reason IR,
ExecutionPlan, Simulation, Knowledge, Playground audit, and compatibility.
