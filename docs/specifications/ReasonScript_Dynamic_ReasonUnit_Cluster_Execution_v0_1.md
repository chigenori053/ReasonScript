# ReasonScript Dynamic ReasonUnit Cluster Execution v0.1

- Contract: `reasonscript-dynamic-reason-unit-cluster/0.1`
- Status: IMPLEMENTED (Experimental Extension)
- Runtime: Rust
- Adapter: thin Python `.rsn` analysis and CLI adapter
- Prerequisite: Cluster Reasoning Runtime Extension v0.1

## Contract

The coordinator is authoritative for dynamic ReasonUnit admission. Workers may propose units but cannot register, activate, suspend, replace, retire, repartition, or commit shared state directly. Proposal processing and all semantic identifiers use canonical JSON and SHA-256; wall-clock time, UUIDs, process identity, receive order, and randomness are excluded.

Dynamic execution is bounded by explicit global, branch, depth, active-unit, proposal, reactivation, step, state, message, and branch limits. Missing bounds or convergence policies are rejected. Budget termination is distinct from successful convergence.

The lifecycle states are `proposed`, `validated`, `rejected`, `registered`, `inactive`, `ready`, `assigned`, `running`, `waiting`, `suspended`, `completed`, `failed`, `retired`, `replaced`, and `cancelled`. Undefined transitions and terminal-state reactivation fail closed.

Plan revisions are canonical, checksummed, atomic, and applied only at logical-step/epoch boundaries. Dynamic dependencies must reference registered units and remain acyclic. State access is declared by read/write/append/reduce sets and is committed through coordinator validation.

## Interfaces

```text
reason cluster dynamic plan <source.rsn> --cluster-config <file> --dynamic-config <file> --json
reason cluster dynamic simulate <source.rsn> --workers <n> --dynamic-config <file> --json
reason cluster dynamic run <source.rsn> --cluster-config <file> --dynamic-config <file> --artifacts-dir <dir> --json
reason cluster dynamic validate <artifact-dir> --json
reason cluster dynamic compare <source.rsn> --cluster-config <file> --dynamic-config <file> --json
reason cluster dynamic test-model --scenario <name> --workers <n> --json
```

No parser syntax is added in v0.1. Generation rules and proposals are supplied through existing analysis metadata, external configuration, or registered TestModels.

## Canonical artifacts

Every successful run emits `dynamic_unit_manifest.json`, `dynamic_unit_lifecycle.jsonl`, `dynamic_unit_proposals.jsonl`, `dynamic_plan_revisions.jsonl`, `dynamic_branch_graph.json`, `dynamic_pruning_report.json`, `dynamic_convergence_report.json`, `dynamic_budget_report.json`, and `dynamic_execution_summary.json`.

Offline validation checks presence and manifest digests, lifecycle legality and sequence, revision checksums and atomicity, graph parent references, proposal trace presence, and budget accounting.

## Compatibility

This is optional and isolated below `ClusterRuntime/src/dynamic`. Existing parser, Reason IR, ExecutionPlan, static Cluster Runtime, single-node runtime, and its nine canonical artifacts retain their existing contracts.

## Acceptance models

DRU-TM-001 through DRU-TM-013 cover generation, multi-generation, duplicate elimination, depth limits, suspension/reactivation, replacement, dynamic dependencies, pruning, convergence, budget termination, worker failure, repeated-run determinism, and 1/2/4 worker equivalence. DRU-TM-MOL-001 covers molecular boundary interaction generation.
