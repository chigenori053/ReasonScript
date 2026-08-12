# ReasonScript v0.5.4.7

## Fixed

- Public user functions can be linked across package source files through
  canonical `module::function` calls, so training and inference share one
  model implementation.
- Nested sibling calls retain intermediate Tensor values until the outer call
  completes, preventing `TSF-018` after `tensor.grad`.
- The native RGO-F1 reader now accepts canonical Python-writer f64 spellings
  by hashing raw record body bytes rather than re-serialized JSON.

## Validation

- Cross-module function, Tensor lifecycle, and RGO-F1 native interoperability
  regression coverage.
