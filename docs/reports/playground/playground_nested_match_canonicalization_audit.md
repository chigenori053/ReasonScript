# Nested Match Canonicalization Audit

Spec: `nested-match-canonicalization/1.0`

Status: implemented

## Results

- Function IR emits `canonical_path` on `MatchSelectionIRNode`.
- Function return transitions use `Score.match.Color.Red|Shape.Circle` for nested match branches.
- ExecutionPlan uses the canonical full path as both `selected_branch` and `path_signature`.
- Simulation emits nested `BranchSelection` events with `branch` and `depth`.
- Knowledge stores `path_signature`, `branch_id`, `evidence_path`, and ordered `enum_match_evidence`.
- Regression coverage is in `tests/test_nested_match_canonicalization.py`.
