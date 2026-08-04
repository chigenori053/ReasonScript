# ReasonScript Integrated Computation Runtime Integration Remediation v0.1

Status: IMPLEMENTED
Phase: Phase 1R — Integrated Computation Runtime Integration Remediation
Target: ReasonScript v0.5.0

## 1. Purpose and scope

This specification connects the existing Tensor numerical kernel to the canonical ReasonScript path:

`.rsn Source → Parser → Namespace Resolution → Semantic Validation → Tensor Registry → Reason IR → ExecutionPlan → Runtime Dispatch → Tensor Backend → Trace → Artifact → Diagnostics`.

Phase 1R is remediation, not a new machine-learning feature phase. It covers Tensor namespace binding, semantic contracts, IR and plan lowering, runtime dispatch, inference functions, finite-value safety, bounded loops, standalone project validation, deterministic probes, artifacts, and regression validation.

Automatic differentiation, training, GPU-specific execution, distributed Tensor, convolution, attention syntax, graph fusion, quantization, sparse Tensor, and a complete dependent-shape type system remain out of scope.

## 2. Public Tensor namespace

The source spelling is `tensor.<function>`. The registry is stable, sorted, versioned `0.1`, callable, deterministic, and backend neutral. Required public functions are:

- Creation and shape: `create`, `reshape`, `transpose`
- Arithmetic: `add`, `subtract`, `multiply`, `divide`, `maximum`
- Matrix: `matmul`
- Reduction/transform: `sum`, `exp`
- Inference: `relu`, `softmax`, `linear`

`relu(x)` lowers to `maximum(x, 0)`. `linear(x, w, bias?)` lowers to `matmul(x, w)` followed by broadcast `add` when bias is present. `softmax(x, axis=-1)` uses max subtraction, exponentiation, reduction, and division.

## 3. Semantic contract

Tensor calls validate function existence, minimum and maximum argument count, Tensor argument kind, supported dtype, rank, rectangular and non-empty creation data, statically knowable reshape sizes, matrix compatibility, broadcast compatibility, and axes. Conditions not knowable at compile time are deferred to runtime.

Semantic results carry Tensor kind, rank, shape, dtype, unknown-dimension markers, and external-value policy. Static rejection uses stable TSF/namespace diagnostics and does not reject genuinely dynamic shapes.

## 4. Reason IR and ExecutionPlan

Every Tensor source call produces a deterministic `tensor_call_NNN` node with:

- qualified function and semantic operation;
- ordered argument representation;
- unique output reference;
- inferred shape/rank/dtype where known;
- high-level-to-lowered operation relationship;
- source reference;
- deterministic operation ID.

The backend-neutral Tensor ExecutionPlan records ordered operations, dependencies, output references, shape/dtype, semantic and lowered operations, abstract backend selection, and source reference. Random UUIDs are forbidden in canonical output.

## 5. Runtime dispatch and trace

The standard source runtime resolves registry entries, materializes arguments, validates inputs, dispatches through `TensorRuntime`, validates outputs, registers external Tensor values, and emits stable traces and metadata. Backend exceptions are normalized into TSF diagnostics; Python tracebacks are never part of user diagnostics.

Tensor metadata includes Tensor ID, shape, rank, dtype, device, backend, lifecycle, and storage reference. Externalized payloads additionally include SHA-256 and byte size.

## 6. Tensor safety and diagnostics

Empty shapes, NaN, positive Infinity, negative Infinity, and operation-generated non-finite values are rejected at creation and operation boundaries.

Stable Phase 1R codes are:

| Code | Meaning |
| --- | --- |
| `TSF-009` | Empty Tensor |
| `TSF-010` | NaN input |
| `TSF-011` | Infinity input |
| `TSF-012` | Non-finite operation result/backend failure |
| `TSF-014` | Unsupported backend operation/device |
| `TSF-015` | Tensor argument type mismatch |
| `TSF-016` | Tensor argument count mismatch |

Existing shape (`TSF-006`/`TSF-008`), axis (`TSF-005`), reshape (`TSF-007`), rectangular input (`TSF-017`), lifecycle, and artifact diagnostics remain supported. Safety diagnostics expose source location, operation reference, Tensor reference where available, severity, and recovery information.

## 7. Loop runtime

The standard integrated runtime executes `for`, bounded `while`, and `loop` with assignment state, `break`, `continue`, iteration counters, deterministic trace, and a configurable hard iteration limit. Exceeding the limit emits `RT-LOOP-001`.

The canonical iterative probe evaluates `x(t+1) = 0.8*x(t) + 1.0` for ten iterations from zero and returns `4.463129088` within floating tolerance.

## 8. Standalone project validation

`reason project-validate [project] --json` is distinct from repository `reason ci`. It validates manifest, sources, semantics, integrated runtime cases, artifacts, optional golden directory, three-run determinism, optional local-test structure, and emits `reasonscript-project-validation/0.1`.

Standalone validation never requires `.github/workflows`, AGENTS.md, compiler sources, internal repository tests, branch policy, or core compatibility suites.

## 9. Canonical probes and artifacts

`reason phase1r-validate --json` generates:

- `artifacts/phase_1r/tensor_namespace_probe`
- `artifacts/phase_1r/tensor_inference_probe`
- `artifacts/phase_1r/invalid_tensor_probe`
- `artifacts/phase_1r/iterative_state_probe`
- `artifacts/phase_1r/project_validation`
- `artifacts/phase_1r/phase_1r_validation_summary.json`

Each probe uses canonical JSON, artifact envelopes/manifests, deterministic ordering, and SHA-256 comparison metadata. Valid probes execute three times. The inference probe uses fixed 3→2 weights in the minimal remediation fixture and must match its reference within `1e-6`, preserve shape/dtype, and sum probabilities to one.

## 10. Acceptance and compatibility

Phase 1R is VALIDATED only when namespace, semantic, IR, ExecutionPlan, runtime, numerical, safety, loop, determinism, project-validation, artifact, golden, and repository regression gates pass. The canonical repository command remains `reason ci --json`.

Existing parser syntax, scalar functions, Runtime Core, Tensor primitive names, artifact fields, diagnostic ordering, canonical serialization, ReasoningModel schema, and existing golden corpus are preserved. Additive schemas are used for integrated runtime, Tensor metadata, comparison, project-validation, and Phase 1R artifacts.

Phase 2 may begin only after Phase 1R and the subsequent Phase 1 revalidation are both VALIDATED.
