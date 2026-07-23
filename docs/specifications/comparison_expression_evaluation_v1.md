# ReasonScript Comparison Expression Evaluation Specification v1.0

Specification ID: comparison-expression-evaluation/1.0

Phase: CSI-BE-002

Status: Implemented

## Scope

The playground branch evaluator supports comparison conditions in function return paths:

- `>`
- `<`
- `>=`
- `<=`
- `==`
- `!=`

Supported operands are `Int`, `Float`, and `Bool` for equality and inequality.

## IR

Function return branch conditions may include a comparison IR node:

```json
{
  "node_type": "ComparisonExpressionIRNode",
  "operator": ">",
  "left": "a",
  "right": "b",
  "result_type": "Bool"
}
```

The runtime evaluates this node against the call-local `evaluation_context` and keeps only the matching `FunctionReturnTransition`.

## Execution Outputs

Selected comparison branches propagate unchanged through:

- `ExecutionPlan.selected_branch`
- `ExecutionPlan.path_signature`
- `SemanticSimulation.selected_branch`
- `Knowledge.evidence_path`
- `Knowledge.comparison_evidence`

Simulation emits `ComparisonEvaluation` before `BranchSelection`.

## Acceptance

The implemented acceptance tests are `CEE-001` through `CEE-006` in `tests/test_comparison_expression_evaluation.py`, with matching `.rsn` fixtures in `tests/cee_001.rsn` through `tests/cee_006.rsn`.
