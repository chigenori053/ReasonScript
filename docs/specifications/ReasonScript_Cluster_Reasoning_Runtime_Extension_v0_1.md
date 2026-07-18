# ReasonScript Cluster Reasoning Runtime Extension v0.1

## Specification status

- Target: ReasonScript 0.5.x Experimental Extension
- Contract: `reasonscript-cluster-*/0.1`
- Implementation language: Rust
- Compatibility: optional extension after the existing ExecutionPlan; Core parser, Reason IR, single-node runtime, and non-cluster artifacts are unchanged.

## Accepted scope

The extension provides deterministic local logical clusters and local worker processes. The Coordinator partitions an existing ExecutionPlan into ReasonTasks, schedules tasks by logical step, dependency depth, partition ID, task ID, and worker ID, enforces barriers, validates messages and state versions, integrates results, and emits replayable artifacts.

Supported modes are `single_process`, `local_process`, and `simulation`. CI requires simulation mode. The default synchronization policy is `barrier`; supported fallback policies are `none`, `single_node`, `abort`, and experimental `partial`.

## Contracts

Canonical configuration uses `reasonscript-cluster-config/0.1`. Canonical task states are `pending`, `ready`, `assigned`, `running`, `waiting`, `completed`, `failed`, `cancelled`, and `skipped`; undefined transitions fail closed.

Messages use `reasonscript-cluster-message/0.1`, SHA-256 checksums, deterministic IDs, and monotonically increasing sequence numbers per run/sender/receiver route. State snapshots use `reasonscript-cluster-state/0.1` and monotonically increasing state versions. Supported merge policies are `replace`, `append`, `set_union`, `ordered_merge`, `numeric_reduce`, and registered deterministic `custom_validated` functions.

Partition IDs are derived from the source ExecutionPlan SHA-256 digest and logical index. Random UUIDs are prohibited in canonical artifacts. Non-deterministic ReasonUnits, cyclic dependencies, atomic boundary violations, and conflicting non-commutative writes are rejected by the planner.

## Runtime and failure policy

Workers cannot execute arbitrary shell commands or access arbitrary files. A worker receives a serializable ReasonTask envelope and returns a state proposal to the Coordinator. Only the Coordinator commits shared state.

Retriable tasks retain their task ID and increment `attempt`. Duplicate commits are rejected. Worker loss can be reassigned when retry policy permits. Corrupt messages, determinism violations, duplicate commits, invalid state merges, and Coordinator inconsistency abort rather than fallback. Insufficient workers may select the recorded `single_node` fallback.

## Required artifacts

Every artifact-producing run emits:

1. `cluster_manifest.json`
2. `cluster_plan.json`
3. `cluster_nodes.json`
4. `cluster_messages.jsonl`
5. `cluster_trace.json`
6. `cluster_state.json`
7. `cluster_diagnostics.json`
8. `cluster_evaluation_report.json`
9. `cluster_run_summary.json`

The manifest records byte sizes and SHA-256 checksums. `reason cluster validate` revalidates artifact presence, manifest checksums, message checksums, node registration, uniqueness, and sequence order.

## CLI

```text
reason cluster plan <source.rsn> --config cluster.json --json
reason cluster run <source.rsn> --config cluster.json --artifacts-dir <dir> --json
reason cluster simulate <source.rsn> --workers 4 --json
reason cluster validate <artifact-dir> --json
reason cluster compare <source.rsn> --config cluster.json --json
reason cluster test-model --scenario <scenario> --workers 4 --json
```

## Validation scenarios

The Dynamic ReasonUnit TestModel covers CRR-TM-001 through CRR-TM-008: independent parallel tasks, dependency chain, fan-out/fan-in, state conflict, worker failure and retry, three-run determinism, single-node equivalence, and fallback. A molecular model additionally validates molecule regions, boundary interaction as its own task, global aggregation, and trace reproduction.

The extension is VALIDATED only when configuration, planner, simulation, two-or-more local processes, state transitions, message ordering/checksums, barriers, worker failure, retry de-duplication, fallback, all nine artifacts, three-run canonical equality, single-node semantic equivalence, all TestModel scenarios, and `reason ci --json` pass.
