# Vision Runtime v0.1

Added the optional safe-Rust `VisionRuntime`, the versioned
`reasonscript-vision-observation/0.1` input contract, deterministic
VisionObservation-to-ReasonUnitObject construction, RUO-T1 detections/input/
embedding Tensor generation, explicit Tensor-axis stable identity mapping,
model and image Evidence provenance, the `reason vision` thin CLI adapter,
canonical phase artifacts, and validation tests.

The language integration adds the typed `vision.infer` and `vision.build_ruo`
functions, Vision public types, semantic diagnostics, `VisionCallIR`, a
capability-aware ExecutionPlan, Rust backend dispatch, atomic canonical `.ruo`
publication, and LSP/Monaco support. The `.ruo` Object retains semantic Units
and uses RUO-T1 Tensor Payloads for numerical detections and embeddings.

Compatibility: programs that do not use `vision.*` retain their existing AST,
IR, plan, Runtime, RUO identity, and RUO-T1 behavior. No production model is
bundled and no inference output is fabricated; the explicit conformance backend
verifies authored test observations and unsupported backends fail closed.
