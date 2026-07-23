# Standard Library

## Status: Does Not Exist Yet

ReasonScript has no standard library today. A repository-wide search for
"standard library," "stdlib," and `std::` finds no hits in any `.rsn`
source, documentation, or ReasonScript-language code — there are no
built-in modules, functions, or types beyond the primitive types described
in [type-system.md](type-system.md#primitive-types) and the language
constructs in [syntax.md](syntax.md).

This page exists so the absence is documented rather than discovered by
searching in vain — if you need string manipulation, collections,
I/O helpers, or similar, they are not provided by the language yet.

## What Might Look Like a Stdlib, But Isn't

Two directories are easy to mistake for a ReasonScript standard library —
neither is one:

- **`sdk/`** — a Python SDK (`sdk.world`, `sdk.reason_graph`,
  `sdk.execution_plan`, `sdk.agent`, `sdk.planning`, `sdk.runtime`) for
  building and driving ReasonScript programs *from Python tooling*. It is
  not code you `import` from within a `.rsn` file. See
  [docs/architecture/worldmodel.md](../architecture/worldmodel.md) for the
  most developed part of it.
- **`toolchain/`** — the Python implementation behind the `reason` CLI
  (`init`, `build`, `run`, `test`, `check`). Also not something you import
  from `.rsn` source. See [docs/references/cli.md](../references/cli.md).

## Working Without One Today

Given there is no stdlib, current `.rsn` programs express logic through:

- Primitive arithmetic and comparisons on `Int`/`Float`/`Bool`/`String`
  (see [type-system.md](type-system.md)).
- User-defined `struct`/`enum` types and `match` (see
  [syntax.md](syntax.md)).
- `Calculation` blocks that call user-defined `fn`s (see
  [syntax.md](syntax.md#calculations)).
- The Reason State model (`Goal`/`State`/`Transition`/`Constraint`/
  `Context`) for anything that needs to reason about state rather than
  compute a pure value — see [semantics.md](semantics.md).

## Tracking

A standard library is not currently a scheduled item in
[ROADMAP.md](../../ROADMAP.md). If you need one, the right first step is a
proposal per
[CONTRIBUTING.md](../../CONTRIBUTING.md#proposing-language-or-runtime-changes).
