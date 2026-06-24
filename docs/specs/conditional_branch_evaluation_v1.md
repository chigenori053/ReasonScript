# ReasonScript Conditional Branch Evaluation Specification v1.0

Specification ID: conditional-branch-evaluation/1.0

Phase: CSI-BE-001

Status: Draft

Depends On:

- function-control-flow/1.0
- knowledge-branch-evidence/1.0
- function-semantic-integration/1.0
- reason-ir/0.1

## Purpose

Function return branches are selected from evaluated Bool conditions, not from structural transition order.

Given:

```rsn
fn Select(flag: bool) -> int {
    if flag {
        return 1
    }

    return 0
}
```

`Select(true)` selects `Select.return.true`; `Select(false)` selects `Select.return.false`.

## Scope

Supported in v1.0:

- `if bool_variable`
- `if true`
- `if false`

Deferred to CSI-BE-002:

- comparisons such as `a > b`
- equality checks such as `x == y`
- general expression evaluation

## IR Model

`ConditionalBranchIRNode` includes an explicit Bool condition type:

```json
{
  "node_type": "ConditionalBranchIRNode",
  "condition": "flag",
  "condition_type": "Bool",
  "true_target": "Select.return.true",
  "false_target": "Select.return.false"
}
```

Function return transitions carry branch evidence and a call-local evaluation context:

```json
{
  "transition_id": "Select.return.false",
  "relation": "FunctionReturnTransition",
  "effect": {
    "branch_conditions": [
      {
        "condition": "flag",
        "condition_type": "Bool",
        "expected_value": false
      }
    ],
    "evaluation_context": {
      "flag": false
    }
  }
}
```

## Selection Algorithm

For each candidate `FunctionReturnTransition`:

1. Evaluate each Bool condition against `evaluation_context`.
2. Keep the transition only when all evaluated values equal `expected_value`.
3. Use the matching transition as the selected branch.
4. Preserve the selected branch ID unchanged through ExecutionPlan, Simulation, and Knowledge.

## Execution Plan

For `result = Select(false)`:

```json
{
  "selected_branch": "Select.return.false",
  "selected_branches": ["Select.return.false"],
  "path_signature": "Select.return.false"
}
```

## Simulation

Simulation emits a `BranchSelection` event:

```json
{
  "event_type": "BranchSelection",
  "branch": "Select.return.false",
  "condition": "flag",
  "value": false
}
```

Nested branches also include a `conditions` array preserving the evaluated path.

## Knowledge

Knowledge units preserve branch evidence:

```json
{
  "target": "Result.state.result",
  "branch_id": "false",
  "path_signature": "Select.return.false",
  "evidence_path": ["Select.return.false"]
}
```

## Nested Branches

For:

```rsn
Score(true, false)
```

the selected path is:

```text
Score.return.a_true_b_false
```

## Validation Rules

- CBE-001: branch condition variable must exist.
- CBE-002: branch condition must resolve to Bool.
- CBE-003: same input must always select the same branch.
- CBE-004: selected branch must propagate unchanged to ExecutionPlan, Simulation, and Knowledge.

## Acceptance Tests

- CBE-001: `Select(true)` selects `Select.return.true`.
- CBE-002: `Select(false)` selects `Select.return.false`.
- CBE-003: Knowledge stores branch ID `false` and path signature `Select.return.false`.
- CBE-004: `Score(true, false)` selects `Score.return.a_true_b_false`.
- CBE-005: repeated `Select(false)` execution is deterministic.
