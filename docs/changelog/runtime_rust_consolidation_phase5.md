# Runtime Rust Consolidation — Phase 5

## Intentional behavior change

- The Rust runtime host now executes all 16 `ruo.*` functions in-process.
- `vision.infer` and `vision.build_ruo` now call the Vision Rust library
  directly instead of falling back through the Python subprocess bridge.
- Rust Vision execution returns the same `vision_trace` records as the Python
  reference runtime, including traced execution requests.
- Native RUO publication now emits canonical RUO-F1 JSONL, validates the
  logical-object seal, confines paths to the resource root, and publishes
  Vision Tensor resources transactionally.
- The runtime consolidation manifest records complete Rust coverage for RUO
  and Vision.

## Compatibility

The public RUO and Vision language contracts, result values, diagnostics,
capability requirements, and output formats are unchanged. Python runtimes
remain available as reference/fallback implementations until the Phase 7
retirement gates are met.
