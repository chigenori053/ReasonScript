# Playground Comparison Expression Evaluation Audit

CSI-BE-002 is implemented in the playground execution pipeline.

## Coverage

- Comparison conditions lower to `ComparisonExpressionIRNode` inside function return branch conditions.
- Function call arguments populate `evaluation_context` for comparison evaluation.
- `>`, `<`, `>=`, `<=`, `==`, and `!=` are supported for numeric operands.
- `==` and `!=` are supported for Bool operands.
- Non-matching `FunctionReturnTransition` branches are pruned before planning and simulation.
- Simulation emits `ComparisonEvaluation` events before `BranchSelection`.
- Knowledge units preserve `comparison_evidence`.
- Nested comparison paths select deterministic branch signatures such as `Compare.return.a_gt_b_and_a_gt_100`.

## Acceptance

`CEE-001` through `CEE-006` are covered by `tests/test_comparison_expression_evaluation.py`.
