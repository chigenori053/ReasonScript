# ReasonScript Transformer Validation Remediation v0.1

Specification ID: `reasonscript-transformer-validation-remediation/0.1`

Status: IMPLEMENTED

Target: ReasonScript v0.5.4.9

## Scope

This specification records the static-validation corrections found while
checking Tensor transformer programs. It preserves the existing compatibility
policy for untyped legacy expressions and does not change the Tensor Training
Foundation contract.

## Corrections

### TVR-001 — `tensor.scalar` has an external scalar result

`tensor.scalar(value)` returns a runtime scalar whose concrete type depends on
the Tensor dtype. Because the surface type system does not carry Tensor dtype,
the validator represents this result as `Unknown`, rather than incorrectly
representing it as `Tensor`. Existing Unknown compatibility rules then allow
valid comparison, logical, assignment, and result contexts while runtime
evaluation remains authoritative for the concrete scalar value.

### TVR-002 — Division returns Float

The `/` operator is true division. Its static result type is `Float` when both
operands are numeric and have the same type, including `Int / Int`. Mixed
`Int`/`Float` arithmetic remains invalid. This prevents an integer result type
from being assigned to a runtime Float value.

Integer division is not introduced by this correction. A future integer
division operator or explicit function requires a separate language proposal.

### TVR-003 — Unknown assignment compatibility is symmetric

An Unknown expected type and an Unknown actual type are both compatible with a
concrete value where the external value type cannot be established statically.
Optional-value checks and concrete type mismatches remain unchanged.

## Preserved Constraints

- `tensor.grad` requires `tensor.parameter` targets (AD-003).
- Statements remain line-oriented; expression operators cannot be continued on
  a new statement line.
- Untyped function parameters cannot be used directly as Boolean conditions.
- Mixed Int/Float arithmetic remains rejected.

## Acceptance

- Tensor scalar comparison and logical regression tests pass.
- `3 / 2` is statically Float and evaluates to `1.5`.
- Unknown-return bindings can be reassigned to concrete Tensor values.
- Existing Tensor, function, and preserved-constraint tests pass.
