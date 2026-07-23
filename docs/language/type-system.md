# Type System

ReasonScript's current type system (Language Surface LS-1) is
**validation-only**: type annotations on variables and Calculation return
values are checked at compile time, but there is no runtime object layout
contract, no type inference, and no generics, traits, interfaces, or
inheritance yet. Normative spec:
[ReasonScript_Language_Surface_Type_Specification_v0.1.md](../specifications/ReasonScript_Language_Surface_Type_Specification_v0.1.md)
(status: Draft).

## Two Type Families

```text
TypeNode = PrimitiveTypeNode { kind: Int | Float | Bool | String | Null }
         | StateTypeNode { kind: Concept | Object | Event | Action | Attribute | Goal | Constraint }
```

### Primitive Types

`Int`, `Float`, `Bool`, `String`, `Null` (the compatibility rules for
`Null` are not yet fully specified — treat it as reserved).

```reasonscript
let age: Int = 20
let score: Float = 0.8

calculation RiskScore -> Float {
    result = score
}
```

Rules:

- **Assignment** uses exact type matching — no implicit coercion.
- **Arithmetic** requires both operands to be the *same* numeric type
  (mixing `Int` and `Float` is a compile-time error).
- **Comparisons** require both operands to be the same known type.
- **Logical operators** require `Bool` operands.

### Reason State Types

The seven `StateTypeNode` kinds are exactly the seven frozen `SemanticUnit`
types described in
[docs/architecture/reasonunit.md](../architecture/reasonunit.md#semanticunit-the-seven-frozen-types):
`Concept`, `Object`, `Event`, `Action`, `Attribute`, `Goal`, `Constraint`. A
variable annotated with one of these resolves to an actual module
declaration of the matching kind:

```reasonscript
let target: Goal = LoanApproval
let rule: Constraint = Adult
```

Resolution rules:

- A `require` reference must resolve to a `ConstraintNode`.
- A `reach`/goal reference must resolve to a `GoalNode`.
- Any other mismatch (e.g. annotating a variable `Goal` but binding it to a
  `Concept` declaration) is a compile-time error.

## Struct and Enum Types

Structs and enums (see [syntax.md](syntax.md#structs) and
[#enums](syntax.md#enums)) are user-defined types used in function
signatures and pattern matching; they are checked structurally by the
pattern-matching validation passes
([struct_pattern_matching_v1.md](../specifications/struct_pattern_matching_v1.md),
[struct_exhaustiveness_v1.md](../specifications/struct_exhaustiveness_v1.md),
[enum_symbol_resolution_v1.md](../specifications/enum_symbol_resolution_v1.md))
rather than by LS-1's primitive/state type rules directly.

## Backward Compatibility

Untyped expressions written before LS-1 remain valid — type annotations
are opt-in, not required, at this stage of the language.

## What's Not Here Yet

- Generics / parametric types.
- Traits / interfaces.
- Inheritance between struct or enum types.
- A runtime type-inference contract (annotations are checked, not
  inferred).
- A standard library type surface — see
  [standard-library.md](standard-library.md).

These are open areas rather than committed roadmap items; see
[ROADMAP.md](../../ROADMAP.md) and
[COMPATIBILITY.md](../../COMPATIBILITY.md) for what's actually scheduled.
