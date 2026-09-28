# DynamicClusterRuntime Integration v1.0 validation

- Target branch: `codex/vision-geometry-runtime`
- Target commit: `26c568dca1c46e0c2f56c42ac085e744940204aa`
- Implementation baseline: `438236d777ecd84f8da1fbb3e882bc5eab533398`
- Validation commit: `29779a8d12f60eb16120734c3beec62552a1e1d2`
- Report commit: the subsequent commit containing this report
- Contract versions: RuntimeTask `reasonscript-runtime-task/1.0`; RuntimeOutput `reasonscript-runtime-output/1.0`; Vision observation `0.1`; Geometry state `1.0`; MIRP graph fragment `0.1`
- Final verdict: **PASS / FROZEN** for the bounded v1.0 contract

## Foundation gates

| Gate | Result | Evidence |
| --- | --- | --- |
| DCR-1 Common contract | PASS | Versioned RuntimeTask/RuntimeOutput schemas, distinct statuses, bounded ClusterLimits |
| DCR-2 Adapter/registry | PASS | Six adapter methods, unique VISION/GEOMETRY registration, explicit `UNSUPPORTED_RUNTIME` |
| DCR-3 Workload/scheduler | PASS | Deterministic estimates and observable LOCAL/CLUSTER decision with mode, workload, threshold, reason |
| DCR-4 Runtime integration | PASS | Registered Vision and Geometry adapters; Vision output consumed by dependent Geometry task |
| DCR-5 Deterministic execution | PASS | Canonical worker identity/lifecycle, sorted merge, UNKNOWN/CONFLICT and provenance preservation, resource limits |
| DCR-6 Semantic equivalence | PASS | Three identity sets × workers 1/2/4 × normal/reversed order × three repetitions |

## A–Z independent validation matrix

| Group | Result | Evidence |
| --- | --- | --- |
| A RuntimeTask schema | PASS | Canonical v1.0 schema; all eight required fields and invalid/future versions tested |
| B RuntimeOutput schema | PASS | Public CLI outputs validated against v1.0 schema |
| C RuntimeAdapter | PASS | Six methods exercised by Vision, Geometry, and delayed test adapter |
| D RuntimeRegistry | PASS | VISION and GEOMETRY registered |
| E duplicate/unsupported | PASS | Duplicate registration rejected; MATH returns `UNSUPPORTED_RUNTIME` and public `UNSUPPORTED` |
| F workload | PASS | Same inputs yield stable estimates and scheduling data |
| G LOCAL | PASS | Single worker and high threshold select local |
| H CLUSTER | PASS | Multiworker workload above threshold selects cluster |
| I ClusterLimits | PASS | Zero, exact, and exceeded operation/memory/state limits; worker bound and timeout |
| J Vision adapter | PASS | Observation produced without Geometry input |
| K Geometry adapter | PASS | GeometryState, relations, and MIRP projection produced |
| L Vision→Geometry | PASS | Explicit dependency consumes Vision observation |
| M dependency graph | PASS | Independent, fan-in, fan-out, and multiple dependency paths |
| N dependency rejection | PASS | Duplicate task, duplicate/missing/self dependency, and cycle rejected |
| O worker lifecycle | PASS | CREATE, DISPATCH, EXECUTE, COLLECT, MERGE, TERMINATE in canonical trace |
| P worker identity | PASS | `worker:{runtime_type}:{task_id}` across configurations |
| Q merge | PASS | Canonical outputs independent of task order and worker count |
| R UNKNOWN | PASS | UNKNOWN survives RuntimeOutput, merged GeometryState, and semantic projection |
| S CONFLICT | PASS | Conflicting primitive identities yield explicit CONFLICT, without order winner |
| T provenance | PASS | Input, observations, primitives, relations, output, trace, and semantic facts retain provenance |
| U operation budget | PASS | Exact limit permitted; one below rejected as RESOURCE_LIMIT |
| V memory/state budget | PASS | Exact serialized limits permitted; one below rejected as RESOURCE_LIMIT |
| W timeout | PASS | Delayed adapter exceeds timeout and returns RESOURCE_LIMIT/TIMEOUT |
| X worker equivalence | PASS | Workers 1, 2, and 4 have equal canonical semantic artifacts |
| Y order equivalence | PASS | Normal and reversed task order compare equal |
| Z Vision→Geometry→MIRP | PASS | Public CLI and Rust end-to-end tests validate MIRP-compatible SemanticState |

## Determinism, equivalence, and semantic evidence

The canonical artifact test runs three independently varied identity sets. Each set changes task IDs, observation IDs, detection IDs, and dependency IDs. For each set it compares three independent repetitions of six configurations: workers 1, 2, and 4, each in normal and reversed task order. This gives **18 executions per identity set, 54 executions total**. GeometryState, SemanticState, RuntimeOutput state and status, provenance, and canonical trace compare equal within each identity set. Worker count 1 selects LOCAL; counts 2 and 4 select CLUSTER. No wall-clock time or OS thread ID participates in these comparisons.

UNKNOWN and CONFLICT are distinct from ERROR. The UNKNOWN test inserts an unevidenced semantic item and verifies the merged state remains UNKNOWN. The CONFLICT test changes a primitive's identity-bearing parameters, adds separate provenance, and verifies explicit conflict rather than a first/last worker winner. The public Vision→Geometry run validates the output schema, MIRP fragment, and task-derived worker IDs. Legacy `reason cluster dynamic visual` and canonical `reason cluster dynamic runtime` remain covered by the integration tests.

## Resource and regression evidence

- Operation budget: below/exact/above behavior checked; exact permitted, above yields RESOURCE_LIMIT.
- Memory and state size: serialized output at exact limit permitted; one byte below rejected. Input/output memory and zero limits also checked.
- Timeout: intentionally delayed Vision adapter with elapsed time beyond `timeout_ms` yields `RESOURCE_LIMIT: TIMEOUT`.
- Anti-cheating: static scan of ClusterRuntime, Vision core, and Geometry core found no fixture identity, filename, generated case ID, or worker-count-specific semantic branch. Varied-identity and task-order execution provides behavioral coverage.
- `./reason ci --json`: **PASS**. Checkout, environment, workspace, diagnostics, artifact validation (6), Golden (2), agent protocol, compatibility (19), and tests all pass. The CI tests phase reports **2,707 passing tests**.
- `cargo test --manifest-path ClusterRuntime/Cargo.toml`: **PASS**, 20 tests (7 ClusterRuntime, 4 Dynamic Reason Unit, 9 Visual/DynamicCluster).
- `python3 -m pytest -q tests/vision_geometry/test_dynamic_runtime.py tests/vision_geometry/test_integration.py`: **PASS**, 6 tests.
- The preceding report recorded 2,709 tests. That historical total is not reproducible by the current canonical CI runner on this checkout. The target-to-validation diff adds one Rust and one Python test and removes none; the current CI count is reported as observed, with no failing or deleted test attributed to this validation.
- No generated artifact or Golden baseline was edited manually. Artifact validation and Golden tests passed through the canonical CI gate.

## Compatibility and known limitations

The canonical RuntimeTask schema now explicitly requires `resource_hint` in newly authored generic tasks. The Rust/CLI compatibility path still accepts legacy JSON without this field; this does not redefine the canonical schema. RuntimeOutput remains at 1.0. No frozen compatibility baseline changed.

Execution uses local threads, not remote or multi-machine workers. Geometry exposes deterministic pair decomposition, but v1.0 schedules at task level; pair-level work is not separately dispatched. Timeout is checked at task-wave boundaries and does not preempt a running adapter. Vision region decomposition, GPU scheduling, additional adapters, and Runtime-internal Work Unit Scheduling remain outside v1.0.

## Final declaration

**DynamicClusterRuntime Integration v1.0 is PASS / FROZEN for the bounded generic runtime orchestration contract defined by RuntimeTask 1.0 and RuntimeOutput 1.0. VisionRuntime and GeometryRuntime are validated as the initial registered runtime adapters. Local and supported clustered execution are semantically equivalent under the validated worker configurations and resource boundaries.**
