# Runtime Rust Consolidation — Phase 6

## Intentional behavior change

- `runtime.search`, `runtime.simulate`, `runtime.predict`, and `runtime.plan`
  now lower to `call_reasoning` in `reason-computation-ir/0.1`.
- The installed Rust host executes these calls in the new in-process
  `reasonscript-reasoning-core` crate.
- RuntimeReal versus HybridRuntime manifest selection now changes the native
  engine provenance returned in reasoning trace.
- The host returns native reasoning trace alongside loop, Tensor, and Vision
  trace, and standalone/project dispatch exposes it to `reason run --trace`.

## Compatibility

The existing Optional result shapes, deterministic values, trace strings,
ExecutionPlan `0.1` structure, and reasoning conversion diagnostic are frozen
and differentially verified against the Python reference engines. The Python
execution architecture remains reference/fallback code until Phase 7.
