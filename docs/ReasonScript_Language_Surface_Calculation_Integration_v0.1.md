# ReasonScript Language Surface Phase 1.6

## Calculation Integration Specification v0.1

Status: VALIDATED

Compatible interfaces:

- `reasonscript-language-surface/0.1`
- `reasonscript-ast/0.1`
- `parser/0.1`
- `compiler/0.1`
- `reason-ir/0.1`
- `execution-plan/0.1`

## 1. Purpose

This specification fixes the Calculation path:

```text
Language Surface Calculation
  -> Statement AST
  -> Calculation AST
  -> Semantic AST
  -> Reason IR
  -> ExecutionPlan
```

Type inference, optimization, constant folding, Runtime evaluation, and JIT
compilation are outside this phase.

## 2. Calculation Node

```text
CalculationNode {
  name: Identifier
  visibility: Visibility
  goal_annotation: Identifier?
  body: Statement[]
}
```

The node and its body are immutable. Source statement order is preserved.
Visibility defaults to `Private`; `pub calculation` produces `Public`.

## 3. Body Contract

Allowed statements are Let, Assignment, If, Match, Expression, and Result.
Require, Goal, and Reach statements are rejected with `CAL-001`.

A Calculation must terminate with exactly one Result on every execution path.
A direct Result must be the final statement. A final If is valid only when it
has an Else and every branch terminates with Result. A final Match is valid
only when every arm terminates with Result.

This path-based rule resolves the control-flow examples while retaining the
single deterministic Result contract.

## 4. Scope

Let bindings are visible after their declaration to the remainder of the
current Calculation block and nested blocks. Nested block bindings do not
escape their block.

An expression identifier must resolve to:

- a preceding local Let binding; or
- a declaration in the containing Module.

Assignment targets must already resolve by the same rule. Function callee
identifiers are operation names and are not variable references.

Duplicate Let bindings are rejected.

## 5. Goal Annotation

`goal:<Identifier>` is stored in `CalculationNode.goal_annotation`. The
identifier must resolve to a `GoalNode` in the containing Module. A missing or
wrong-kind reference is rejected with `CAL-V008`.

The annotated Goal becomes the target of the Calculation's terminal semantic
transition. Without an annotation, the Module's normal goal target is used.

## 6. Semantic Projection

Top-level Calculation statements project in source order:

| Statement | Semantic relation |
|---|---|
| Let | Expression-specific transition |
| Assignment | `StateUpdateTransition` |
| Expression | `CallTransition` |
| If / Match | `DecisionTransition` |
| Result | `ResultTransition` |

Expression-specific arithmetic relations retain the existing precise names,
including `AddTransition` and `MultiplyTransition`. Result expression data is
stored in the transition effect while the relation remains
`ResultTransition`.

Generated transition IDs include the one-based statement index so repeated
assignment to one target remains unique and deterministic.

## 7. Reason IR and ExecutionPlan

The semantic transitions compile through the unchanged compiler to
`reason-ir/0.1`. ExecutionPlan steps are generated from Reason IR transition
order, so Calculation source order is retained.

Calculation visibility, Goal annotation, target name, source Statement AST,
and expression data are stored in the existing transition effect extension.
No Reason IR or ExecutionPlan schema field is added.

## 8. Serialization

Calculation AST serializes with canonical node names and all four fields.
`calculation.schema.json` references the canonical Calculation definition in
the Language Surface AST schema. Deserialization accepts older Calculation
documents without `visibility` and assigns `Private`.

## 9. Validation Rules

| Rule | Contract |
|---|---|
| CAL-V001 | Valid immutable Calculation node |
| CAL-V002 / CAL-001 | Allowed statements only |
| CAL-V003 / CAL-010 / CAL-011 | One terminal Result per path |
| CAL-V004 / CAL-012 | Result finality |
| CAL-V005 / CAL-020 / CAL-021 | Variable and binding resolution |
| CAL-V006 | Expression validity |
| CAL-V007 | Source statement ordering |
| CAL-V008 | Goal annotation resolves to GoalNode |

## 10. Conformance

The executable validation suite is `calculation_integration_tests/`. It covers
Layers A through E from the Phase 1.6 validation matrix, including semantic
projection, Reason IR, ExecutionPlan, schema validation, and round trip.
