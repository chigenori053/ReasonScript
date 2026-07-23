# ReasonScript Nested Match Canonicalization Specification v1.0

Specification ID: nested-match-canonicalization/1.0

## Purpose

Nested match branches are serialized as an ordered semantic path instead of a parser-shaped string.

Current internal form:

```text
Score.match.Color.Red_and_match.Shape.Circle
```

Canonical form:

```text
Score.match.Color.Red|Shape.Circle
```

## Rules

- Each selected enum pattern is serialized as `Enum.Variant`.
- Nested selections are joined with `|` in execution order.
- A full path signature is `<Function>.match.<Pattern1>|<Pattern2>`.
- A nested branch id omits the function prefix: `<Pattern1>|<Pattern2>`.
- Parser-specific fragments such as `_and_match`, `PatternNode`, and `EnumValuePatternNode` must not appear in canonical branch ids.

## Required Artifacts

- Function IR `MatchSelectionIRNode` stores `canonical_path`.
- ExecutionPlan uses the canonical full path for `selected_branch` and `path_signature`.
- Simulation emits one `BranchSelection` event per nested match level with `depth`.
- Knowledge stores the full `path_signature`, canonical `branch_id`, `evidence_path`, and ordered enum match evidence.
