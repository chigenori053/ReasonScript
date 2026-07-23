# Structured Function Control Flow Specification v1.0

Specification ID: function-control-flow/1.0
Phase: FSI-2
Status: Draft

Depends on:
- function-semantic-integration/1.0
- reasonscript-language-surface/0.1
- reason-ir/0.1

## Purpose

FSI-2 extends ReasonScript functions from a single terminal-return model to a structured control-flow model. Function bodies may contain branch statements, and semantic validation verifies that every reachable execution path terminates in a `ReturnStatementNode`.

## Return Model

The deprecated FN-012 rule is removed:

> `ReturnStatementNode` must be the final statement.

The replacement rule is path based:

> A function is valid when every reachable execution path ends with `ReturnStatementNode`.

## Validation Rules

- FCF-001: Not all execution paths return.
- FCF-002: Unreachable statements.
- FCF-003: Unreachable branch. Optional warning in v1.0.
- FCF-004: Condition must be Bool.

## Control Flow IR

Function IR may contain:

- `ConditionalBranchIRNode`
- `MergeIRNode`
- `ReturnIRNode`

Example:

```rsn
fn Select(flag: bool) -> int {
    if flag {
        return 1
    }

    return 0
}
```

The branch IR records distinct terminal return paths:

```json
{
  "node_type": "ConditionalBranchIRNode",
  "condition": "flag",
  "true_target": "Select.return.true",
  "false_target": "Select.return.false"
}
```

## Execution Semantics

Each return path is represented as a `FunctionReturnTransition`. Multiple return paths are allowed for one function:

- `Select.return.true`
- `Select.return.false`

Execution plans and knowledge extraction preserve the selected branch as path evidence.

## Acceptance

FSI-2 is complete when:

- Single terminal return restriction is removed.
- CFG-style function branch IR is generated.
- Multiple return paths are supported.
- All-path return analysis is implemented.
- `FunctionReturnTransition` supports branch targets.
- ExecutionPlan preserves selected branch.
- Knowledge preserves branch evidence.
- FCF-001 through FCF-005 pass.
