# Runtime Rust Consolidation Phase 2

- Added shared `toolchain.runtime_dispatch` for standalone and project Rust
  host selection, capability propagation, and fallback classification.
- `reason build` now emits and validates
  `target/computation_ir/package.json` plus a runtime-support artifact.
- Project `reason run` executes the built Computation IR without recompiling
  source when Rust supports the package.
- Added qualified imported-function lowering for multi-file packages.
- Project output now exposes `execution_mode` and `runtime_dispatch` using the
  same engine names and fallback reasons as standalone execution.
