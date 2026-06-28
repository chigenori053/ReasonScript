# ReasonScript Pattern Identity Normalization Specification v1.0

Specification ID: `pattern-identity-normalization/1.0`

Phase: MSI-008A

Status: Draft

## Purpose

Pattern Identity defines one canonical semantic identifier for the selected
pattern across Reason IR, ExecutionPlan, Simulation, and Knowledge artifacts.
It preserves existing fields such as `selected_branch`, `path_signature`,
`branch_id`, `canonical_path`, and `selected_pattern` for compatibility.

## Identity Model

Every selected pattern exposes:

```json
{
  "pattern_id": "Score.match.Color.Blue",
  "pattern_type": "Enum",
  "canonical_path": "Score.match.Color.Blue"
}
```

`pattern_id` always equals the selected canonical path. The identity is
deterministic, immutable, human-readable, and serialization-safe.

## Pattern Types

Supported `pattern_type` values are:

- `Literal`
- `Enum`
- `Optional`
- `Struct`
- `NestedStruct`
- `OrAlternative`
- `Guard`

Future pattern families may add additional values without changing the schema.

## Canonical Rules

Pattern IDs follow `<Function>.match.<CanonicalPattern>`.

Examples:

- Enum: `Score.match.Color.Red`
- Struct: `Score.match.Point.x0_bindy`
- Nested: `Score.match.Person.position|Position.x0`
- Optional: `Score.match.some`
- Guard: `Score.match.Point.x0|guard.x_gt_y`
- OR pattern: `Score.match.Color.Blue`

For OR patterns, only the selected alternative becomes the Pattern Identity.

## Artifact Requirements

- Every `MatchSelectionIRNode` contains `pattern_identity`.
- ExecutionPlan contains `pattern_identity`.
- Simulation contains `pattern_identity`.
- Every `BranchSelection` event references the same `pattern_identity`.
- Knowledge units contain `pattern_identity`.
- Existing identity-like fields remain present for backward compatibility.

## Validation Rules

- `PIN-001`: Every `MatchSelectionIRNode` must contain Pattern Identity.
- `PIN-002`: Pattern IDs must be deterministic.
- `PIN-003`: Pattern IDs must be unique within one function.
- `PIN-004`: ExecutionPlan, Simulation, and Knowledge expose identical Pattern Identity.
- `PIN-005`: Pattern Identity must equal the canonical path.
- `PIN-006`: Pattern type must match the selected pattern category.

## Acceptance

`tests/pin_001.rsn` through `tests/pin_007.rsn` and
`tests/test_pattern_identity_normalization.py` cover enum, struct, optional,
nested, guard, OR, and repeated-compilation identity propagation.
