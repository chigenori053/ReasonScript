# Runtime Rust Consolidation — Phase 4

## Intentional behavior change

- The Rust runtime host now implements all 65 frozen `tensor.*` functions.
- `slice`, `narrow`, `gather`, `concat`, `stack`, `relu`, `softmax`, `linear`,
  `conv2d`, `max_pool2d`, and `avg_pool2d` no longer trigger Python fallback.
- Their differentiable operations now participate in the Rust autograd tape
  with Python-compatible VJPs.
- Tensor execution with trace enabled remains in Rust and returns Tensor trace
  and metadata.
- Rust Tensor I/O now enforces per-operation filesystem capabilities,
  resource-root confinement, safe `.rstensor` paths, overwrite behavior, and
  artifact limits.
- Rust Tensor creation and conversion now enforce the frozen Tensor resource
  policy limits.

## Compatibility

The public Tensor function manifest is unchanged. This phase closes runtime
coverage gaps without changing ReasonScript source syntax or function
signatures. The runtime consolidation baseline changes only from unsupported
to implemented for the eleven completed functions and records Rust Tensor
trace as the active path.
