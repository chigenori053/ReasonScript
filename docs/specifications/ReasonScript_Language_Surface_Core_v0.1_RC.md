# ReasonScript Language Surface Core v0.1 RC

Status: RELEASE CANDIDATE

Compatible interfaces:

- `reasonscript-language-surface/0.1`
- `reasonscript-ast/0.1`
- `parser/0.1`
- `compiler/0.1`
- `reason-ir/0.1`
- `execution-plan/0.1`
- `reasonscript-calculation-semantics/0.1`

## 1. Purpose

Language Surface Core v0.1 is the standard deterministic mapping from
human-readable ReasonScript source to Surface AST, Semantic AST, Reason IR,
and ExecutionPlan.

```text
Source Code
  -> Language Surface Parser
  -> Surface AST
  -> Semantic AST
  -> Compiler
  -> Reason IR
  -> ExecutionPlan
```

## 2. Modules and Imports

```text
module finance {
}

pub module finance {
}

import finance.loan
import finance.loan as loan
```

Module visibility and body order are retained in the immutable Surface AST.
Import paths are non-empty identifier sequences.

## 3. Declarations and Relations

Core declarations are Concept, Object, Event, Action, Attribute, Goal, and
Constraint.

Supported relations are:

- `IsA`
- `PartOf`
- `Cause`
- `Dependency`
- `Constraint`
- `Temporal`
- `Spatial`
- `Similar`

Both relation endpoints must resolve to declarations in the same Module.

## 4. Transitions

The validated v0.1 Transition form retains the Phase 1.1 state mapping:

```text
transition Approve {
    Draft -> Approved
    require Adult
    goal LoanApproval
    reach LoanApproval
}
```

Require, Goal, Reach, If, Match, and ExpressionStatement are allowed in a
Transition body. References must resolve to the corresponding declaration
kind. The state mapping supplies the semantic source and fallback target;
Reach may select the final target.

## 5. Calculations

```text
calculation RiskScore {
    result = income * factor
}

pub calculation RiskScore goal:RiskEvaluation {
    let score = income * factor
    result = score
}
```

A Calculation has immutable local Let bindings, ordered statements, optional
public visibility, and an optional Goal annotation. Every execution path must
terminate with exactly one Result. Goal annotations resolve to Goal
declarations.

Calculation projection is fixed as:

| Statement | Semantic relation |
|---|---|
| Let | Expression-specific Transition |
| Assignment | `StateUpdateTransition` |
| Expression | `CallTransition` |
| If / Match | `DecisionTransition` |
| Result | `ResultTransition` |

## 6. Statements

The canonical Statement hierarchy is:

```text
StatementNode
  LetStatementNode
  AssignmentStatementNode
  ResultStatementNode
  RequireStatementNode
  GoalStatementNode
  ReachStatementNode
  ExpressionStatementNode
  IfStatementNode
  MatchStatementNode
```

Statement placement is validated before Semantic AST projection.

## 7. Expressions and Patterns

Expression literals are Integer, Float, Boolean, String, and Null. Core
operators include unary `-` and `!`, arithmetic `+ - * / %`, comparison
`== != > >= < <=`, logical `&& ||`, member access, calls, and explicit
parenthesized expressions.

Match patterns are IdentifierPattern, LiteralPattern, and WildcardPattern.

The parser uses deterministic precedence:

```text
postfix
  -> unary
  -> multiplicative
  -> additive
  -> comparison
  -> logical AND
  -> logical OR
```

## 8. Validation

The release candidate fixes these rule families:

- `AST-V001` through `AST-V007`
- `EX-V001` through `EX-V005`
- `PT-V001` through `PT-V004`
- `ST-V001` through `ST-V007`
- `CAL-V001` through `CAL-V008`

Validation guarantees immutable AST values, source order preservation,
reference resolution, valid statement placement, Calculation scope, Result
finality, and valid Goal annotations.

## 9. Serialization

Every serialized AST object has a canonical `node_type`. For every supported
Surface AST root and standalone Expression, Pattern, Statement, or
Calculation:

```text
deserialize(serialize(node)) == node
```

Canonical serialization validates against the schemas under
`frontend/schemas/`.

## 10. Compatibility and Determinism

Equal source produces structurally equal Surface AST, Semantic AST, Reason IR,
and ExecutionPlan values. Existing semantic AST, parser, compiler, Reason IR,
ExecutionPlan, Calculation Semantics, and Runtime interface versions are
unchanged.

The Surface `ProgramNode` remains an additive source-facing root and projects
to one semantic `ModuleNode` per Surface Module.

## 11. Release Candidate Gate

Release requires:

- Phase 1.1 PASS;
- Phase 1.2 PASS;
- Phase 1.3 PASS;
- Phase 1.6 PASS;
- Core RC Conformance PASS;
- full Python regression PASS;
- HybridRuntime regression PASS;
- Semantic AST, Reason IR, and ExecutionPlan compatibility PASS;
- serialization and deterministic replay PASS.

The executable gate is
`release/language-surface-v0.1-rc/run_release_validation.py`.
