# ReasonScript Tensor Standard Functions v0.1

Specification ID: `reasonscript-tensor-standard-functions/0.1`
Status: VALIDATED

This implementation provides the complete v0.1 `tensor.*` primitive set as
pure, deterministic standard functions. Tensor storage and numeric operations
are owned by a replaceable backend; Runtime Core receives only an external
`TensorValueRef` containing identity and metadata.

The normative function contracts are exposed by `TensorRuntime.contracts`.
The Python reference backend supports `bool`, `i32`, `i64`, `f32`, and `f64` on
`cpu`, NumPy-compatible broadcasting, negative axes, immutable results, resource
limits, TSF diagnostics, execution-plan records, simulation traces, and inline
or checksum-addressed external artifacts.

High-level neural operations remain library compositions. The conformance tests
construct ReLU, stable Softmax, Linear, and a tiny feed-forward pass exclusively
from the standard Tensor primitives.

Compatibility: Tensor support is isolated under `frontend.tensor` and introduces
no required third-party dependency or behavioral change to non-Tensor programs.
