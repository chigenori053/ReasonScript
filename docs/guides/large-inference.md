# Large graph inference

`examples/inference_scale/main.rsn` exposes two evidence-bound graph inference
entries running on the production Rust VM. Both use MRA_Test's Unit and
EvidenceBinding records. The original MRA_Test source and saved results are
retained. Its Foundation model's separate fact-capacity limit is not changed.

## Summary inference for large or branching graphs

Call `UnifiedB::Summarize` with `units`, `trusted`, `entities`, `start`, `goal`,
`depth`, and `work_budget`. This entry calls the native
`graph.summarize(units, trusted, entities, start, goal, depth, work_budget)`
primitive. Replace an exhaustive request's `path_budget` with `work_budget`:

```sh
cd examples/inference_scale
../../reason run main.rsn --entry UnifiedB::Summarize --inputs /absolute/input.json --json
```

The `GraphSummary` result has:

| Field | Meaning |
| --- | --- |
| `status` | `VERIFIED`, `HYPOTHESIS`, `UNKNOWN`, `CONTRADICTED`, or `INVALID`. |
| `dependencies` | Complete union of unknown/hypothesis unit IDs on any start-to-goal walk of length 1 through `depth`, in input-unit order. |
| `proof_path` | One shortest verified witness; equal-length ties follow input-unit order. Empty if none exists or admission/work limits prevent completion. |
| `admitted` | Whether the request completed admission and the whole summary computation. |
| `resource_limit` | Whether the deterministic work budget was exhausted. |
| `work` | Records, array items, adjacency entries, and proof links charged to the work budget. |

Summary mode does not return `all_paths` or their count. Its status and
unknown-dependency **set** agree with bounded exhaustive inference when that
inference completes. Dependency ordering deliberately follows input order;
exhaustive mode follows the first encountered goal walks. Cycles and repeated
edges are permitted as bounded walks. A zero-length path does not prove a goal,
including when `start == goal`; a nonempty verified cycle can.

Evidence bindings must match evidence ID, unit ID, subject, predicate, object,
polarity, and revision. Units require nonempty provenance, a positive current
revision, and a non-revoked state. Verified units require bound evidence;
contradicted units are excluded from positive paths. Traversal uses predicate `1`
and polarity `1`; direct negative edges use predicate `1` and polarity `-1`,
matching the MRA adapter. Duplicate unit IDs reject
admission. A verified direct negative edge changes a reachable goal to
`CONTRADICTED`, while retaining any independently verified positive witness.

The native primitive checks the relevant record field types even when called
from source with custom struct names. Units need the fields `unit_id`,
`semantic_status`, `evidence`, `revision`, `provenance`, `subject`, `object`,
`predicate`, `polarity`, `current_revision`, `negative_evidence`, and `revoked`.
Bindings need the seven matching fields above. Additional fields are allowed.
The full MRA_Test records satisfy this contract.

The implementation hashes complete evidence bindings, builds forward/reverse
adjacency, and runs three breadth-first searches: all active forward edges,
reverse edges from the goal, and verified forward edges. An unknown edge
belongs to a goal walk exactly when its shortest reachable prefix plus the edge
plus its shortest goal suffix fits the depth. This avoids enumerating paths or
propagating a dependency set per path. Expected time and memory are linear in
input records and edges, including evidence/provenance items and string hashing;
the number of possible walks does not determine the stored state.

`depth` must be positive; `work_budget` must be in 1..100,000,000. Invalid bounds
produce `GRAPH-004`; invalid record types produce `GRAPH-003`. Work exhaustion
returns `UNKNOWN`, `admitted=false`, `resource_limit=true`, and empty dependencies
and proof. Partial traversal is never reported as a completed summary.

## Exhaustive paths for bounded inputs

`UnifiedB::Derive` retains the original input shape, including `path_budget`,
and returns every ordered path as `all_paths`. `Classify` and `VerifyProof` also
remain available. Sorted ID/evidence/subject indexes replace repeated scans.
`VerifyProof` independently checks the full evidence/revision binding.

```sh
cd examples/inference_scale
../../reason run main.rsn --entry UnifiedB::Derive --inputs /absolute/input.json --json
```

Enumerating all walks can require exponential output even with perfect indexes.
`path_budget` bounds generated walks per depth and completed paths; exhaustion
returns `admitted=false`, `resource_limit=true` with no verified proof. Use summary
mode when the decision, representative proof, and unknown-dependency union suffice.

## Resource limits

The example opts into 10,000,000 typed input nodes, 512 MiB of compact input
JSON, and 10,000,000 block visits per function call. Nodes include every scalar,
struct field, and container, not just Knowledge Units. Projects without explicit
settings retain the default 100,000 input nodes. The byte limit applies after
transport parsing, before typed VM input allocation; it does not limit process RSS.

The bridge independently defaults to a 30-second watchdog. Set
`REASONSCRIPT_RUNTIME_TIMEOUT=120` for a longer bounded source run. Native graph
work is charged through `work`, independently of VM instruction/block counts.
Input limits, work limits, wall time, and RSS are separate bounds. Admission or
resource refusal is not successful inference.

## Reproduce measurements

Build the host, then select a fresh output directory:

```sh
cargo build --release --offline --manifest-path ReasonRuntime/Cargo.toml -p reasonscript-computation-runtime-cli
python3 scripts/benchmark_graph_summary.py --out /tmp/graph-summary-new-run
```

The default matrix covers 200,000/250,000 physical units, seeds 401/402/403,
sparse and branching graphs, with fresh native processes. Sparse cases have
one 16-edge path containing an unknown edge. Branching cases contain 16 choices
at each of 128 layers (16^128 walks), plus disconnected filler units to reach
the requested size. All evidence shares an ID but binds to distinct units.
These are generated stress fixtures using the MRA record contract, not blind
held-out research inputs.

The benchmark monitors each native process with `ps`, enforces 120 seconds and
4 GiB RSS, and checks exact OS-reported peak RSS after completion. Monitoring
must be available; restricted environments may need permission to inspect the
benchmark's own child process. Each result must have the expected status and
complete dependency set. A separate Python check validates the returned proof's
connectivity, revision, provenance, polarity, and full evidence binding. JSONL
records retain resource failures; request/source/host hashes and raw responses
are saved. Wall time includes native file parsing, ABI admission, inference,
serialization, and independent witness verification, excluding source compilation
and fixture generation. Native peak RSS excludes the Python controller's memory.
Use `--repeats`, `--sizes`, `--seeds`, `--seconds`, and `--rss-gib` to set a matrix.

For saved MRA_Test inputs and oracles:

```sh
python3 scripts/benchmark_indexed_inference.py --summary \
  --mra-root /absolute/MRA_Test --out /tmp/mra-summary-new-run.jsonl
```

Omit `--summary` for the earlier exhaustive comparison. Both benchmark tools pin
the release host (`--host` overrides it). The general bridge also prefers the
local release host over debug; `REASONSCRIPT_RUNTIME_HOST` remains an override.
The saved-input benchmark includes hashing/encoding/startup in wall time and
has no RSS watchdog. Its summary mode checks status, dependency set, and any
returned witness's membership in the frozen oracle's paths.

The graph primitive currently executes on CPU. GPU execution is not implemented
or benchmarked; summary semantics remove the exponential enumeration workload
before considering hardware acceleration.
