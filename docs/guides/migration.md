# Migration

ReasonScript is pre-1.0 (`0.1.0-alpha`) and versions its interfaces layer by
layer rather than as one whole-project semantic version — see
[COMPATIBILITY.md](../../COMPATIBILITY.md). This guide covers the migration
paths that actually exist today. There is currently no "migrating from
language X" guide, because ReasonScript does not (yet) provide automated
interop or transpilation from other languages.

## Migrating from the Legacy Core Grammar

If you have programs written in the original minimal grammar
(`goal`/`derive`/`prove`/`apply`/`compute`/`converge`/`rollback`, one
statement per line — documented in
[grammar.md](../specifications/grammar.md) and
[semantics.md](../specifications/semantics.md)), they predate the current
Language Surface (modules, functions, structs, enums, pattern matching; see
[docs/language/syntax.md](../language/syntax.md)). There is no automatic
converter. To migrate by hand:

| Legacy statement | Surface equivalent |
| --- | --- |
| `goal <symbol>` | A `Goal`-typed value or the module's implicit terminal condition — see [docs/language/semantics.md](../language/semantics.md#core-concepts) |
| `compute <a> <op> <b>` | An expression inside a `fn` or `calculation` block |
| `apply <state>` | The committed effect of a `Transition`, produced by running a `calculation`/`fn` through `reason build && reason run` |
| `prove <proof>` | Not directly expressible in the current surface; validation now happens through `Constraint` declarations and compiler-level checks |
| `converge <symbol>` | `Convergence::converge` at the runtime level (see [docs/architecture/tensor.md](../architecture/tensor.md#execution-and-convergence)), not currently a surface-syntax construct |
| `rollback <state>` | Automatic: a failed commit triggers a traced reverse `StateDelta`, per [docs/language/semantics.md](../language/semantics.md#rollback-and-proof-failure) |

In practice, migrating means re-expressing the program's intent as a
module with functions/Calculations rather than translating line by line —
the legacy grammar is a much smaller, flatter model.

## Migrating Between Frozen Interface Versions

When a layer version bumps (e.g. a future `reason-ir/0.2`), the change and
its impact will be documented in [CHANGELOG.md](../../CHANGELOG.md) under
that release, with the old version's frozen guarantees remaining valid for
existing `0.1` artifacts per [COMPATIBILITY.md](../../COMPATIBILITY.md).
There is no interface version bump yet beyond what's listed there, so
there's nothing to migrate between at this time — check
[COMPATIBILITY.md](../../COMPATIBILITY.md#frozen-interfaces) before
depending on a specific layer version in production tooling.

## Migrating a Project's Runtime Backend

Switching a project between runtime backends is a one-line change in
`reason.toml`:

```toml
[runtime]
backend = "RuntimeReal"    # or "HybridRuntime"
```

See [docs/architecture/runtime.md](../architecture/runtime.md) for what
each backend actually does differently — they are not drop-in equivalent
for every workload (`HybridRuntime` is oriented around ambiguity
resolution and the Semantic Language v0.2 engines; `RuntimeReal` is the
general-purpose execution engine).

## From Other Languages

There is no supported migration path from Python, Rust, or any other
general-purpose language into ReasonScript today — no transpiler, no
foreign-function bridge beyond what the `dto/` bindings provide at the
Reason IR boundary (see
[docs/architecture/compiler.md](../architecture/compiler.md#3-reason-ir--frontendcompilercompilerpy)).
If your use case needs this, treat it as a fresh implementation exercise
using [docs/guides/first-project.md](first-project.md) as a starting point.
