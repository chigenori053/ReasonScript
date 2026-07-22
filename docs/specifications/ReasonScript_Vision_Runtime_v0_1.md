# ReasonScript Vision Runtime v0.1

Specification ID: `reasonscript-vision-runtime/0.1`  
Status: VALIDATED

## Purpose

Vision Runtime is an optional safe-Rust boundary that converts an explicit,
provenance-bearing `reasonscript-vision-observation/0.1` document into a
ReasonUnitObject with both semantic entities and canonical RUO-T1 Tensor
Payloads. It does not infer truth from confidence and does not make Tensor row
positions semantic identities.

## Contract

The runtime validates finite coordinates, closed-interval confidence, stable
observation and track identities, SHA-256 image/model provenance, input Tensor
shape, and embedding width. Its initial Object contains image provenance,
AtomicReasonUnits for tracks, observed states, normalized evidence, frame-to-track
relations, dense little-endian `.ruot` resources, and explicit Tensor axis-0
identity mappings.

The default Tensor set is:

- `detections`: `[N,6]` as `x,y,width,height,confidence,class_index`;
- `input`: the optional model input Tensor;
- `embeddings`: optional `[N,D]` features when every detection supplies one.

Model execution is owned by implementations of the Rust `VisionBackend` trait.
The v0.1 repository ships only the explicit `observation-json-test` conformance
backend, which verifies authored observation provenance and never fabricates
model output. A future Burn/ONNX adapter may implement the trait without
changing the Observation-to-RUO contract.

## Compatibility

The companion `reasonscript-vision-language-integration/0.1` profile adds an
optional `vision.*` namespace, typed Reason IR operations, ExecutionPlan steps,
and integrated-runtime dispatch. Programs that do not use the namespace retain
their existing syntax, IR, Runtime, RUO identity, and RUO-T1 semantics.

## Validation

The phase requires Rust unit tests, observation and RUO build CLI tests,
RUO-U1 validation, RUO-T1 resource validation, Golden preservation, Agent
Protocol validation, and `reason ci --json`.
