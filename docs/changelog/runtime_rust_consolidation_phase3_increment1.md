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

Phase 3 remains `IN_PROGRESS`: native loop/Tensor trace parity and remaining
current-runtime gaps must pass before Phase 4 begins.
