# ReasonScript v0.5.4.9

## Added

- Added `reason init <name> --template agent`, which generates tool-neutral
  `AGENTS.md` instructions and a `DRAFT` project specification under
  `SPECIFICATIONS/` while preserving the existing minimal template.

## Fixed

- Corrected the surface type of `tensor.scalar` so transformer comparison and
  logical expressions are not rejected as Tensor operands.
- Aligned division type checking with runtime true-division semantics by
  returning Float for `Int / Int`.
- Made Unknown assignment compatibility symmetric for legacy function results.

## Preserved compatibility constraints

- Tensor autograd still requires explicit `tensor.parameter` targets.
- Statements remain single-line; multiline parameter lists remain supported.
- Explicit parameter annotations remain required for Boolean control-flow use.
