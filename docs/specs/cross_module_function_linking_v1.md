# Cross-Module Function Linking v1.0

Specification ID: `cross-module-function-linking/1.0`

## Purpose

A package is a closed ReasonScript program formed from every `.rsn` source in
`src/`. Public functions may be imported and called from another module, so
training and inference sources can refer to one model implementation.

## Call syntax and resolution

```rsn
import model
result = model::Forward(input)
```

The callable is resolved to its canonical `module::function` identity before
type checking, IR lowering, and execution. `module.function()` is not a user
function call and fails with `FN-011`; a dot remains member access syntax.

Unqualified calls are permitted only for local functions and public functions
explicitly exposed by an import. Private functions remain unavailable across
module boundaries.

## Package compilation

`reason check` and `reason build` parse each source unit, aggregate their
modules, then resolve the complete package namespace. Per-file resolution is
not permitted for package imports. Generated IR remains module-scoped, while a
cross-module `FunctionCallIRNode.function` records the callee's canonical
identity.

## Runtime

The integrated evaluator keeps a package function registry keyed by canonical
function identity. A function executes with bindings from its declaring module,
not the caller's module.

## Validation

- Public cross-file qualified calls compile and execute.
- Import aliases and unqualified imported public functions retain visibility
  checks.
- Missing/private/ambiguous imports retain namespace diagnostics.
- Train and inference IR may be compared by canonical `FunctionCallIRNode`
  target to prove use of the same model function.
