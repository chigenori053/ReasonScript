# DynamicClusterRuntime Integration v1.0 validation

- Baseline commit: `438236d777ecd84f8da1fbb3e882bc5eab533398`
- Result commit: the `codex/vision-geometry-runtime` branch tip containing this report
- Runtime versions: RuntimeTask/RuntimeOutput `1.0`, Vision observation `0.1`, Geometry state `1.0`, MIRP graph fragment `0.1`
- Final status: **PASS** (not FROZEN; no independent review claimed)

## Foundation gates

| Gate | Result | Evidence |
| --- | --- | --- |
| DCR-1 Common contract | PASS | Versioned RuntimeTask and RuntimeOutput, generic ClusterLimits, status envelope, JSON schemas |
| DCR-2 Adapter/registry | PASS | RuntimeAdapter, RuntimeRegistry, unique VISION and GEOMETRY registration, explicit unknown rejection |
| DCR-3 Workload/scheduler | PASS | Adapter workload/decomposition, deterministic LOCAL/CLUSTER decision with workload, threshold, reason |
| DCR-4 Runtime integration | PASS | Vision and Geometry execution through registered adapters; Vision dependency output consumed by Geometry |
| DCR-5 Deterministic execution | PASS | Stable worker ID and lifecycle, canonical task merge, provenance, UNKNOWN and CONFLICT outcomes, explicit budgets |
| DCR-6 Semantic equivalence | PASS | Three independent runs for workers 1/2/4 and reversed tasks with varied task/object identities |

## Validation matrix

| IDs | Result and check |
| --- | --- |
| A–B | PASS: versioned task and output schemas validated through the public CLI |
| C–E | PASS: adapter methods, registry uniqueness, unknown runtime and invalid schema rejection |
| F–I | PASS: Vision/Geometry estimates, LOCAL/CLUSTER thresholds, zero/exact/exceeded limits |
| J–L | PASS: Vision and Geometry adapters, explicit Vision→Geometry dependency |
| M–N | PASS: independent, fan-in and fan-out tasks; missing, self, duplicate and cyclic dependency rejection |
| O–P | PASS: six lifecycle events and task-derived worker identities |
| Q–T | PASS: stable merge and semantic trace, UNKNOWN, CONFLICT, provenance |
| U–W | PASS: operation boundary, input/output memory and state size, elapsed timeout |
| X–Z | PASS: workers 1/2/4, reverse order, end-to-end Vision→Geometry→MIRP SemanticState |

## Repetition and regression

The canonical-equivalence test runs three independently varied task and object identity sets. Each set executes three repetitions of all six worker/order combinations (1, 2, 4 workers × original/reversed input). It compares GeometryState, MIRP semantic state, each runtime output, provenance, and canonical reasoning trace. Fixture-specific IDs, filenames, and worker-count-dependent semantic values are absent from the implementation.

`cargo test --manifest-path ClusterRuntime/Cargo.toml` passes existing ClusterRuntime, DynamicCluster and Visual tests. Python Vision/Geometry integration and the generic CLI/schema test pass. `./reason ci --json` passes workspace, diagnostics, artifact validation, Golden, agent protocol, compatibility, and full tests (2,709 passing tests). Existing non-Visual DynamicCluster tests remain green.

## Compatibility and limits

The existing `reason cluster dynamic visual` command and legacy task JSON without `schema_version` remain accepted. `reason cluster dynamic runtime` is the generic command; newly authored tasks should include the versioned schema field. The worker implementation uses local threads. Geometry exposes deterministic pair decomposition, while each task is currently evaluated as one worker unit. Timeout is checked at task-wave boundaries and does not preempt an adapter call. This version does not implement remote execution, image region segmentation, or arbitrary runtime adapters.
