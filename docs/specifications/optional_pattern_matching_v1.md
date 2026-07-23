# ReasonScript Optional Pattern Matching Specification v1.0

Specification ID: optional-pattern-matching/1.0

## Purpose

Optional values participate in the existing match semantic pipeline. `some(x)` selects the `some` branch and binds `x` to the contained value. `none` selects the `none` branch.

## Canonical Branches

- `some(x)` serializes as `some`.
- `none` serializes as `none`.
- Full path signatures use the normal match form: `Score.match.some` and `Score.match.none`.
- Nested optional matches use canonical nested path joining, for example `Score.match.some|some`.

## IR

```json
{ "node_type": "OptionalSomePatternNode", "binding": "x" }
```

```json
{ "node_type": "OptionalNonePatternNode" }
```

`MatchSelectionIRNode` stores `canonical_path`, matching the branch path components.

## Runtime Artifacts

- ExecutionPlan stores the selected optional branch as `selected_branch` and `path_signature`.
- Simulation emits `OptionalPatternEvaluation` before `BranchSelection`.
- Knowledge stores `optional_match_evidence` with the selected optional kind.
- `some(...)` bindings are added only to the selected branch evaluation context.
