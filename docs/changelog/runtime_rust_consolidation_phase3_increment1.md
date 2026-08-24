# Runtime Rust Consolidation Phase 3 — Increment 1

- Computation IR function IDs are now module/package-qualified, preventing
  collisions when different modules declare the same symbol.
- Qualified calls retain their resolved canonical names through Python IR and
  Rust VM execution.
- Rust support preflight classifies unsupported Tensor, RUO, and Vision calls
  before process execution.
- Rust `RuntimeError` now carries the nearest IR `source_span`; host diagnostics
  publish it as `source_location`.
- The Runtime Result JSON Schema now describes diagnostic source locations.

- Added explicit loop trace instructions to Computation IR and matching Python
  IR/Rust VM implementations for while, for, loop, break, and continue.
- Scalar/control-flow trace requests now remain on Rust; domain operations
  whose trace is not yet native are rejected by trace preflight.

Phase 3 is complete for the existing integrated runtime's scalar, collection,
function, and control-flow surface. Tensor trace/metadata is Phase 4 scope;
Vision trace is Phase 5 scope. Map/Set/Optional literals and pattern matching are
not supported by the current Python integrated runtime either and therefore
remain language-extension work, not Python-to-Rust runtime migration.
