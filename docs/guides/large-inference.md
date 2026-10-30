# Bounded large graph inference

Use `examples/inference_scale/main.rsn` for the indexed variant of MRA_Test's
`UnifiedB::Derive`, `Classify`, and `VerifyProof` entries. Execution uses the
production Rust VM. The original MRA_Test source and saved results are not
modified. This example does not change the application's Foundation model or
its separate fact-capacity limit.

The input shape matches MRA_Test's evidence-bound adapter: `units`, `trusted`
EvidenceBindings, `entities`, `start`, `goal`, `depth`, and `path_budget`.
Evidence bindings must match the evidence ID, unit ID, subject, predicate,
object, polarity, and revision. Revoked or stale units cannot verify a proof.
Duplicate unit IDs reject admission. Unknown dependencies remain explicit.

```sh
cd examples/inference_scale
../../reason run main.rsn --entry UnifiedB::Derive --inputs /absolute/input.json --json
```

The example's `reason.toml` opts into 5,000,000 typed input nodes, 512 MiB of
compact input JSON, and 10,000,000 block visits per function call. Nodes count
all struct fields and containers, not just Knowledge Units. The runtime keeps
the default 100,000 input-node limit for projects without an explicit setting.
The input-byte limit applies after transport JSON parsing; it is not a process
memory limit. Use an external process/RSS watchdog where one is required.

There are independent limits:

- The Python-to-native bridge watchdog defaults to 30 seconds. Set
  `REASONSCRIPT_RUNTIME_TIMEOUT=120` for a longer bounded run.
- `runtime.max_loop_iterations` limits visits to each IR block per function
  call. It is not a semantic reasoning-step count.
- `path_budget` bounds generated walks per depth and completed paths. Exhaustion
  returns `admitted=false`, `resource_limit=true`, with no verified proof.
- Input elements, bytes, depth, and application-specific capacities remain
  separate admission checks. A refusal is not successful inference.

The original adapter repeatedly copied the growing ID array, scanned it for
duplicates, scanned every trusted binding for every unit, and scanned every
unit for every frontier node. The indexed variant sorts IDs once to detect
adjacent duplicates, sorts evidence by unit ID once for binary lookup, and sorts units by
subject for binary lookup of outgoing edges. The stable subject sort preserves
source order within each node, including proof and dependency ordering.
`VerifyProof` independently rechecks evidence and revisions against an ID index.
Index construction costs O(n log n + t log t); evidence searches cost
O(log t + equal-unit-ID bucket size). Path enumeration can still grow exponentially
with branching and depth; bounded budgets remain necessary. Many bindings with
the same unit ID can also require scanning a large bucket.

This workload is scalar graph traversal and string matching. The example uses
CPU indexing and does not route it through Tensor/GPU operations.

## Reproduce against MRA_Test

The native bridge prefers a local release host over a local debug build;
`REASONSCRIPT_RUNTIME_HOST` still overrides selection. Build the local host first, then run the read-only benchmark with a fresh output
path. It requires MRA_Test's saved `run-20261030-rs-02` inputs and oracles.

```sh
cargo build --release --offline --manifest-path ReasonRuntime/Cargo.toml -p reasonscript-computation-runtime-cli
python3 scripts/benchmark_indexed_inference.py \
  --mra-root /absolute/MRA_Test --out /tmp/inference-new-run.jsonl
```

The default matrix covers random/math inputs, seeds 401/402/403, 10,000/100,000
units, depths 2/4/8/16, and three fresh-process executions per case. Each result
must be admitted, retain the oracle status and unknown dependencies, and return
exactly the oracle's ordered paths. Failures and timeouts remain failures.
The benchmark pins the local release host for the whole run (`--host` selects
another binary). JSONL records include host/source/input/oracle hashes and native metrics. Elapsed
wall time includes hashing, encoding, process startup, ABI admission, and
inference; it is not the earlier MRA_Test driver's VM-only cold/warm timing.
The benchmark does not impose an RSS watchdog or claim a GPU speedup.
Use `--source` to measure the original adapter on smaller inputs, and select
`--sizes`, `--seeds`, `--depths`, and `--repeats` to bound a comparison.
