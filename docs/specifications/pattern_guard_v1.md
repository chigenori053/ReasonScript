# ReasonScript Pattern Guard Specification v1.0

Specification ID: `pattern-guard/1.0`

Pattern guards add a `when <bool-expression>` filter to match arms. Evaluation order is pattern match, branch-local binding, guard evaluation, then branch selection.

Guards do not contribute to exhaustiveness. A guarded catch-all still needs an unguarded fallback.

Guarded match selections lower to `GuardExpressionIRNode` and include the guard segment in canonical paths, for example:

`Score.match.Point.bindx_bindy|guard.x_gt_y`

Simulation emits `GuardEvaluation` before `BranchSelection`, and Knowledge preserves `guard_evidence`.
