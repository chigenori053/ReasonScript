# DL Runtime Usability Corrections

- `reason run` executes package-wide cross-module calculations through the
  integrated runtime and supports `--entry` and `--trace`.
- Tensor named arguments now support sparse optional arguments and `none` for
  optional Tensor slots.
- Large result Tensors are emitted as checksum-addressed external artifacts.
- Added functional SGD, Momentum, Adam, AdamW, and learning-rate schedulers.
