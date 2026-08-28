# ReasonScript RUO First-Class Runtime Completion v1.0

Status: ACCEPTED — implemented
Date: 2026-08-24

## Scope

This increment closes the gap between RUO-N2 compiler metadata and executable
ReasonScript values. `ReasonObject` and the opaque `ruo.*` result types are
legal in function signatures and local bindings. A `ReasonObjectBindingNode`
has static type `ReasonObject`; each `ruo.*` call has a declared result type and
checks statically knowable argument kinds.

Product execution loads declared Objects through the Rust runtime host only and
requires explicit filesystem-read capability. Paths remain confined to the
execution resource root. Transactions preserve snapshot isolation and explicit
commit/rollback semantics; saving additionally requires filesystem-write
capability. The AST evaluator and Python Computation IR interpreter are retained
only as independent reference implementations for differential tests.

## Compatibility

A bound `ReasonObject` is accepted at snapshot or transaction entry points.
This preserves RUO-N2 source examples while taking the required immutable
snapshot or transaction at runtime. Opaque RUO values have no direct member
mutation surface.

## Validation

- A bound Object may be aliased and passed into and returned from a typed
  function.
- `ruo.object_id(1)` is rejected statically with `RUO-N2-009`.
- Rust host execution matches the Python reference implementations for
  first-class Object programs and all 16 `ruo.*` operations.
- Execution without filesystem-read capability is rejected.

## Native boundary

The Rust Computation VM decodes Object bindings, verifies canonical `.ruo`
files in `reason-object-core`, confines compiler-produced paths, and executes
all 16 frozen `ruo.*` operations in-process. Product execution has no Python
fallback; unsupported or failed native operations produce structured
diagnostics. RUO-W1 world-level multi-project atomic cutover remains a separate
phase.
