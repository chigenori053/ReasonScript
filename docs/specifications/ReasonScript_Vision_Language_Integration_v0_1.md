# ReasonScript Vision Language Integration v0.1

Specification ID: `reasonscript-vision-language-integration/0.1`  
Status: VALIDATED

## Purpose

Vision Language Integration exposes the safe-Rust VisionRuntime to ReasonScript
programs while preserving explicit provenance, capability checks, RUO identity,
and RUO-T1 Tensor semantics.

## Language Contract

The `vision` standard namespace defines these typed functions:

- `vision.infer(Path, Path) -> VisionObservation`
- `vision.build_ruo(VisionObservation, Path) -> VisionBuildResult`

The public types are `VisionModel`, `VisionObservation`, and
`VisionBuildResult`. Paths are project-relative, may not escape the project
root, and Object output uses the lowercase `.ruo` extension.

## Lowering and Execution

Calls lower to typed `VisionCallIR` operations and an ExecutionPlan using the
native operation names `vision_infer` and `vision_build_ruo`. Inference requires
`filesystem_read`; Object publication requires `filesystem_write`.

Model execution is dispatched through the Rust `VisionBackend` boundary. The
v0.1 conformance backend, `observation-json-test`, verifies image and model
provenance before importing test observations. Unsupported production backends
fail explicitly and never fabricate detections.

## RUO Publication

`vision.build_ruo` emits semantic ReasonUnits plus RUO-T1 Tensor Payloads. Tensor
resources are checksum-verified and atomically renamed before the canonical
RUO-F1 writer commits the `.ruo` file. The `.ruo` file is the commit point;
failed publication rolls back newly created resources.

## Tooling and Compatibility

LSP and IDE completion/highlighting include the Vision functions and types.
Programs that do not use `vision.*` retain their existing AST, IR, plan, and
runtime behavior. Validation requires Rust tests, frontend/runtime tests, RUO-U1
and RUO-T1 validation, Golden coverage, and `reason ci --json`.
