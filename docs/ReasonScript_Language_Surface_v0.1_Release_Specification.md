# ReasonScript Language Surface v0.1 Release Specification

Status: RELEASED

Release date: 2026-06-14

Version: `reasonscript-language-surface/0.1`

Compatible interfaces:

- `reasonscript-ast/0.1`
- `parser/0.1`
- `compiler/0.1`
- `reason-ir/0.1`
- `execution-plan/0.1`
- `reasonscript-calculation-semantics/0.1`

## 1. Purpose

ReasonScript Language Surface v0.1 is the normative source language for the
ReasonScript Platform. It defines this deterministic mapping:

```text
ReasonScript Source
  -> Surface AST
  -> Semantic AST
  -> Reason IR
  -> ExecutionPlan
```

The release guarantees deterministic parsing, immutable AST values, source
order preservation, stable serialization, semantic projection compatibility,
Reason IR compatibility, and ExecutionPlan compatibility.

## 2. Architecture

The Language Surface has six layers:

1. Module and Namespace
2. Declarations and Relations
3. Expressions and Patterns
4. Statements
5. Calculations
6. Type Annotations

## 3. Modules, Imports, and Namespaces

```text
module finance {
}

pub module finance {
}

import finance
import finance.RiskScore
import finance as loan
import finance.RiskScore as risk
```

Every named declaration shares one module namespace. The supported categories
are Concept, Object, Event, Action, Attribute, Goal, Constraint, Transition,
and Calculation. Duplicate names fail with `NS-001`.

Import resolution produces canonical qualified names. Aliases are unique,
only public symbols are importable, and ambiguous unqualified imports are
rejected.

Unqualified lookup order is:

1. Local scope
2. Module namespace
3. Imported symbols

Qualified names use `::`:

```text
finance::RiskScore
loan::RiskScore
```

The canonical AST representation is `QualifiedIdentifierNode`.

## 4. Visibility

Visibility defaults to Private. A Calculation is public only when declared
with `pub`:

```text
pub calculation RiskScore {
    result = 1
}
```

Other declaration categories inherit module visibility. Only public symbols
may be imported.

## 5. Declarations and Relations

Supported declarations:

```text
concept Person
object User
event Login
action Approve
attribute Age
goal LoanApproval
constraint Adult
```

Supported relations:

- `IsA`
- `PartOf`
- `Cause`
- `Dependency`
- `Constraint`
- `Temporal`
- `Spatial`
- `Similar`

Relation endpoints resolve within the current module namespace.

## 6. Transitions

The normative Transition syntax requires one state mapping:

```text
transition Approve {
    Draft -> Approved
    require Adult
    goal LoanApproval
    reach LoanApproval
}
```

Allowed Transition statements are RequireStatement, GoalStatement,
ReachStatement, IfStatement, MatchStatement, and ExpressionStatement.

## 7. Expressions and Patterns

Literal categories are Integer, Float, Boolean, String, and Null.

Supported operators and constructs:

- unary `-` and `!`;
- arithmetic `+ - * / %`;
- comparison `== != > >= < <=`;
- logical `&& ||`;
- Call Expression;
- Member Access;
- Parenthesized Expression;
- Qualified Identifier.

Patterns are IdentifierPattern, LiteralPattern, and WildcardPattern.

## 8. Statements

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

Statement placement is validated before semantic projection.

## 9. Calculations

```text
calculation RiskScore {
    result = income * factor
}

pub calculation RiskScore goal:RiskEvaluation {
    let score = income * factor
    result = score
}
```

A Calculation has immutable local scope, preserves statement order, and
supports optional Goal, visibility, and return type annotations. Every
execution path terminates with exactly one Result.

## 10. Type System

Primitive types:

- `Int`
- `Float`
- `Bool`
- `String`
- `Null`

State types:

- `Concept`
- `Object`
- `Event`
- `Action`
- `Attribute`
- `Goal`
- `Constraint`

```text
let score: Float = 0.8
let target: Goal = LoanApproval

calculation RiskScore -> Float {
    result = score
}
```

Types are validation-only contracts and do not define runtime object layout.

## 11. Serialization and Determinism

Every serialized node contains `node_type`.

```text
deserialize(serialize(node)) == node
```

Equal source produces structurally equal Surface AST, Semantic AST, Reason IR,
and ExecutionPlan values.

## 12. Validation Families

The normative validation families are:

- `AST-V001` through `AST-V007`
- `EX-V001` through `EX-V005`
- `PT-V001` through `PT-V004`
- `ST-V001` through `ST-V007`
- `CAL-V001` through `CAL-V008`
- `TYPE-V001` through `TYPE-V008`
- `NS-V001` through `NS-V007`

## 13. Release Certification

Release status is granted because these gates pass:

- Phase 1.1 AST Mapping
- Phase 1.2 Expression and Pattern
- Phase 1.3 Statement
- Phase 1.6 Calculation
- LS-1 Type
- LS-2 Namespace
- Core conformance
- Full Python regression
- HybridRuntime regression
- Reason IR compatibility
- ExecutionPlan compatibility
- Serialization compatibility

## 14. Release Decision

ReasonScript Language Surface v0.1 is RELEASED as of 2026-06-14.

It is a fixed Platform v0.1 Alpha interface. Subsequent primary development
moves to the Runtime and Semantic layers, including Operational Semantics
v0.2, ExecutionPlan v0.2, HybridRuntime integration, and ReasonGraph
integration.

