# Optional Pattern Matching Audit

Spec: `optional-pattern-matching/1.0`

Status: implemented

## Results

- Parser accepts lowercase `some(x)` and `none` optional patterns.
- Optional patterns lower into `OptionalSomePatternNode` and `OptionalNonePatternNode`.
- Function return transitions use `Score.match.some`, `Score.match.none`, and nested canonical paths such as `Score.match.some|some`.
- ExecutionPlan and Simulation preserve canonical optional path signatures.
- Simulation emits `OptionalPatternEvaluation` before `BranchSelection`.
- Knowledge stores `optional_match_evidence`.
- `some(...)` branch bindings are scoped to the selected branch evaluation context.
