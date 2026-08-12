# F15/F16/F18 language and runtime corrections

- Package compilation now resolves all source modules together and supports
  public cross-module user functions through canonical `module::function`
  calls.
- User-facing dot calls to a resolved function report `FN-011` with the
  required `::` syntax instead of being misdiagnosed as an enum issue.
- Evaluated sibling call arguments remain Tensor lifecycle roots until their
  enclosing call returns, preventing `TSF-018` after `tensor.grad`.
- Native RGO-F1 loading now validates raw canonical body bytes rather than a
  Rust re-serialization, restoring Python/Rust finite-f64 interoperability.
