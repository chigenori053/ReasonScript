# ReasonScript Language Surface LS-1 Type Specification v0.1

Status: Draft for Validation

Compatible:

- `reasonscript-language-surface/0.1`
- `reasonscript-ast/0.1`
- `parser/0.1`
- `compiler/0.1`
- `reason-ir/0.1`
- `execution-plan/0.1`

## 1. Purpose

LS-1 adds validation-only type annotations to Variables and Calculation return
values. Types do not define runtime object layout.

The following features are outside LS-1: type inference as a public language
contract, generic types, traits, interfaces, and inheritance.

## 2. Type Model

`TypeNode` is the union of:

```text
PrimitiveTypeNode { kind: Int | Float | Bool | String | Null }
StateTypeNode {
  kind: Concept | Object | Event | Action | Attribute | Goal | Constraint
}
```

Every serialized concrete type contains `node_type`.

## 3. Syntax

```text
let age: Int = 20
let score: Float = 0.8

calculation RiskScore -> Float {
    result = score
}
```

The AST fields are:

```text
LetStatementNode {
    identifier
    expression
    type_annotation?
}

CalculationNode {
    name
    goal_annotation?
    body
    visibility
    return_type?
}
```

## 4. Compatibility

Primitive assignment uses exact matching. `Null` compatibility remains
deferred in LS-1 and is accepted without defining nullable semantics.

Arithmetic requires two equal numeric types. Mixed `Int` and `Float`
arithmetic is invalid. Comparison operands must have equal known types.
Logical operands must be `Bool`.

Untyped legacy expressions whose external value type cannot be established
remain valid for compatibility with Language Surface 0.1.

## 5. State Type Integrity

A State type annotation on an identifier expression resolves the referenced
module declaration and requires the matching declaration kind.

```text
let target: Goal = LoanApproval
let rule: Constraint = Adult
```

`require` references must resolve to `ConstraintNode` (`TYPE-010`).
`reach` and goal references must resolve to `GoalNode` (`TYPE-011`).

## 6. Validation Rules

| Rule | Contract |
|---|---|
| `TYPE-V001` | Type name is known |
| `TYPE-V002` | Type node and typed references resolve |
| `TYPE-V003` | Assignment and return types are compatible |
| `TYPE-V004` | Arithmetic operands are compatible |
| `TYPE-V005` | Comparison operands are compatible |
| `TYPE-V006` | Logical operands are Bool |
| `TYPE-V007` | Goal type integrity |
| `TYPE-V008` | Constraint type integrity |

## 7. Compiler Compatibility

Type annotations serialize in the Surface AST and are copied into Calculation
semantic transition effect data. LS-1 does not add fields to Reason IR or
ExecutionPlan schemas, and types have no runtime layout effect.

