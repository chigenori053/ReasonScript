# ReasonScript RUO First-Class Runtime Completion v1.0

Status: ACCEPTED — implemented
Date: 2026-08-24

## Scope

This increment closes the gap between RUO-N2 compiler metadata and executable
ReasonScript values. `ReasonObject` and the opaque `ruo.*` result types are
legal in function signatures and local bindings. A `ReasonObjectBindingNode`
has static type `ReasonObject`; each `ruo.*` call has a declared result type and
checks statically knowable argument kinds.

The AST computation evaluator and the Python Computation IR interpreter load
declared Objects only with explicit filesystem-read capability. Paths remain
confined to the execution resource root. Immutable inspection and snapshot
operations execute through the shared `frontend.reason_object_runtime`
dispatcher. Transactions preserve snapshot isolation and explicit
commit/rollback semantics; saving additionally requires filesystem-write
capability.

## Compatibility

A bound `ReasonObject` is accepted at snapshot or transaction entry points.
This preserves RUO-N2 source examples while taking the required immutable
snapshot or transaction at runtime. Opaque RUO values have no direct member
mutation surface.

## Validation

- A bound Object may be aliased and passed into and returned from a typed
  function.
- `ruo.object_id(1)` is rejected statically with `RUO-N2-009`.
- AST and Python Computation IR execution produce identical calculation
  results for a first-class Object program.
- Execution without filesystem-read capability is rejected.

## Native boundary

The Rust Computation VM decodes Object bindings, verifies canonical `.ruo`
files through `NativeReasonUnitRuntime`, confines compiler-produced paths, and
executes `object_id`, `snapshot`, `resolve`, `status`, and `diagnostics`.
Operations not yet implemented natively return `RT-UNSUPPORTED-001`, causing
the default runner to use the validated Python implementation. RUO-W1
world-level multi-project atomic cutover remains a separate phase.
