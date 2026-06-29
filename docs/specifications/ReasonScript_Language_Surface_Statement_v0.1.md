# ReasonScript Language Surface Phase 1.3

## Statement Specification v0.1

Status: VALIDATED FOR THE DEFINED PHASE 1.3 SURFACE

Compatible interfaces:

- `reasonscript-language-surface/0.1`
- `reasonscript-ast/0.1`
- `parser/0.1`
- `compiler/0.1`
- `reason-ir/0.1`
- `execution-plan/0.1`
- `reasonscript-calculation-semantics/0.1`

## 1. Purpose

Phase 1.3 fixes the executable statement layer:

```text
Source Statement
  -> Statement AST
  -> validated placement and references
  -> semantic AST projection
  -> compiler
```

Declarations, expressions, and patterns were fixed by Phases 1.1 and 1.2.
Type checking, type inference, optimization, Runtime execution, and planner
selection remain outside this phase.

## 2. Statement Hierarchy

```text
StatementNode
|- LetStatementNode
|- AssignmentStatementNode
|- ResultStatementNode
|- RequireStatementNode
|- GoalStatementNode
|- ReachStatementNode
|- ExpressionStatementNode
|- IfStatementNode
`- MatchStatementNode
```

Every Statement is immutable and serializes with its concrete `node_type`.

The Phase 1.1/1.2 names `LetNode`, `IfNode`, and `MatchNode` remain Python API
aliases for source compatibility. New parsing and serialization always use
the Phase 1.3 canonical `*StatementNode` names.

## 3. Let Statement

```text
let score = 100
```

maps to:

```text
LetStatementNode {
  identifier: "score"
  expression: ExpressionNode(...)
}
```

ST-001 and ST-002 require a valid identifier and expression. ST-003 rejects a
duplicate immutable binding in the same statement list.

## 4. Assignment Statement

```text
score = score + 1
```

maps to:

```text
AssignmentStatementNode {
  target: "score"
  expression: ExpressionNode(...)
}
```

Assignment is valid only in a Calculation body. ST-010 rejects it in Module,
Transition, and nested Transition statement bodies.

## 5. Result Statement

```text
result = score
```

maps to:

```text
ResultStatementNode {
  expression: ExpressionNode(...)
}
```

A Calculation body MUST contain exactly one Result Statement, and it MUST be
the final top-level statement. A Result is not valid in a nested if/match arm
or Transition body.

Phase 1.3 supersedes the Phase 1.1 provisional separate
`CalculationNode.result` field. Result now participates in statement order:

```text
CalculationNode {
  name
  goal_annotation
  body: tuple<StatementNode>
}
```

## 6. Require Statement

```text
require Adult
```

maps to `RequireStatementNode(constraint="Adult")`.

The reference MUST resolve to a `ConstraintNode` in the same Surface Module.
Missing references fail ST-030. A symbol of another declaration kind fails
ST-031.

The parser also accepts the earlier spelling `requires Adult` and normalizes
it to the same node.

## 7. Goal Statement

Inside a Transition:

```text
goal LoanApproval
```

maps to `GoalStatementNode(goal="LoanApproval")`.

At Module level the same source prefix remains a `GoalNode` declaration.
Context determines the unambiguous mapping. Missing goals fail ST-040 and
wrong-kind references fail ST-041.

## 8. Reach Statement

```text
reach LoanApproval
```

maps to `ReachStatementNode(goal="LoanApproval")`. The Goal reference is
required and MUST resolve to a `GoalNode`.

During semantic projection, the last top-level Reach Statement determines the
semantic Transition target. This is a compile-time mapping only; Goal
satisfaction and execution remain governed by Operational Semantics.

## 9. Expression Statement

```text
publish(order)
```

maps to:

```text
ExpressionStatementNode {
  expression: ExpressionNode(CallExpressionNode(...))
}
```

ST-060 requires the root expression to be `CallExpressionNode`. Bare
identifiers, literals, arithmetic, comparisons, and member access without a
call are invalid Expression Statements.

## 10. If Statement

```text
if score > 80 {
  reach Approved
}
elif score > 50 {
  reach Review
}
else {
  reach Rejected
}
```

maps to one `IfStatementNode` with ordered `ElseIfStatementNode` branches and
an optional `ElseStatementNode`. The condition is a Phase 1.2 Expression.
ST-071 requires a non-empty primary body.

Nested statements inherit the placement context of the containing Transition
or Calculation. Result is never permitted in a nested branch.

## 11. Match Statement

`MatchStatementNode` contains a Phase 1.2 Expression and ordered
`MatchArmNode` values. Each arm contains a Phase 1.2 Pattern and a non-empty
Statement body.

ST-080 requires the expression. ST-081 requires at least one arm and a
non-empty body for every arm.

## 12. Placement Rules

| Container | Allowed |
|---|---|
| Module body | declarations, imports, relations, Transition, Calculation |
| Transition body | Require, Goal, Reach, If, Match, ExpressionStatement |
| Calculation body | Let, Assignment, If, Match, ExpressionStatement, Result |

Statements directly in a Module body are invalid. Nested If and Match bodies
use the same allowed set as their enclosing Transition or Calculation,
except Result is restricted to the top-level Calculation body.

## 13. Reference Resolution

The Surface Module namespace is built before statement validation.

```text
RequireStatement -> ConstraintNode
GoalStatement    -> GoalNode
ReachStatement   -> GoalNode
```

Existence and declaration kind are checked separately. Reference failure
occurs before semantic projection and compiler invocation.

## 14. Ordering and Integrity

Statement order is represented by immutable tuples and preserved by parsing,
serialization, projection, and generated semantic Transition order.

Calculation integrity:

1. all top-level statements retain source order;
2. exactly one Result Statement exists;
3. Result is the final statement;
4. duplicate Let bindings in one statement list are invalid.

## 15. Serialization

The normative schema is:

```text
frontend/schemas/statement.schema.json
```

It references the recursive Statement definitions in
`language_surface_ast.schema.json`. Every concrete Statement has a
`node_type`, including nested branches and match arms.

```text
statement_from_json(to_json_value(statement)) == statement
```

## 16. Semantic Projection

### 16.1 Transition

Transition statements map without changing `reason-ir/0.1`:

- Require references become the semantic Transition guard;
- Goal references are preserved in effect data;
- Reach selects the Transition target;
- the full ordered Statement list is serialized into effect data;
- If, Match, and call statements remain structurally available to later
  compiler phases.

### 16.2 Calculation

Every top-level Calculation Statement creates one ordered semantic Transition:

| Statement | Projection |
|---|---|
| Let | State-variable step with expression relation |
| Assignment | `StateUpdateTransition` |
| ExpressionStatement | `CallTransition` |
| If / Match | `DecisionTransition` |
| Result | Calculation Result transition to the semantic Goal |

The serialized Statement is stored in Transition effect data. Statements that
contain expressions also expose the structured Expression separately.

## 17. Validation Rules

| Rule | Meaning |
|---|---|
| ST-V001 | Statement type is known |
| ST-V002 | Statement placement is valid |
| ST-V003 | Goal and Constraint references resolve |
| ST-V004 | Calculation has exactly one Result |
| ST-V005 | Goal reference kind is valid |
| ST-V006 | Constraint reference kind is valid |
| ST-V007 | Statement order and Result finality are preserved |

The numbered ST-001 through ST-081 rules are enforced by parser and validator
checks described in the preceding sections.

## 18. Conformance

Implementation:

- `frontend/language_surface/nodes.py`
- `frontend/language_surface/parser.py`
- `frontend/language_surface/validation.py`
- `frontend/language_surface/integration.py`
- `frontend/schemas/statement.schema.json`

Validation:

```sh
python3 -m unittest discover -s statement_tests -p 'test_*.py' -v
```

Phase 1.1, Phase 1.2, Calculation Semantics, compiler, Reason IR, and Runtime
regressions remain mandatory.
