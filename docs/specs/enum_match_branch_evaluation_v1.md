# ReasonScript Enum Match Branch Evaluation Specification v1.0

Specification ID: `enum-match-branch-evaluation/1.0`

Phase: MSI-002A

Status: Implemented

## Purpose

Enum-valued function arguments participate in runtime match evaluation. A call such as `Score(Color.Red)` builds an evaluation context:

```json
{
  "color": {
    "enum": "Color",
    "variant": "Red"
  }
}
```

Match arms using enum patterns are represented canonically:

```json
{
  "node_type": "EnumValuePatternNode",
  "enum_name": "Color",
  "value_name": "Red"
}
```

The selected branch identifier is serialized as `<Function>.match.<Enum>.<Variant>`, for example `Score.match.Color.Red`.

## Runtime Rules

- Enum patterns match only when both enum name and variant name equal the input enum value.
- Enum mismatch is a non-match.
- Unknown enum variants in match patterns are rejected with `ESR-001`.
- Default arms are evaluated only after prior non-default enum patterns fail.
- Only selected function return branches participate in planning and knowledge extraction.

## Artifact Propagation

For `result = Score(Color.Red)`, execution plan and simulation expose:

```json
{
  "selected_branch": "Score.match.Color.Red",
  "path_signature": "Score.match.Color.Red"
}
```

Simulation emits `EnumPatternEvaluation` followed by `BranchSelection`.

Knowledge preserves:

```json
{
  "path_signature": "Score.match.Color.Red",
  "branch_id": "Color.Red",
  "evidence_path": ["Score.match.Color.Red"],
  "enum_match_evidence": {
    "enum": "Color",
    "variant": "Red"
  }
}
```

## Acceptance Coverage

- EMB-001: `Color.Red` selects `Score.match.Color.Red`.
- EMB-002: `Color.Blue` selects `Score.match.Color.Blue`.
- EMB-003: knowledge preserves enum evidence and `from_simulation`.
- EMB-004: simulation emits `EnumPatternEvaluation`.
- EMB-005: unmatched enum branch is absent from the selected path.
- EMB-006: repeated execution is deterministic.
