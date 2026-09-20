# ReasonScript standard library

Standard-library calls are namespaced and validated before native execution.
This page is a practical index; exact Tensor signatures are available from
`reason tensor-manifest --json` and the frozen baseline in
`contracts/tensor_function_manifest.json`.

## Runtime

| Call | Purpose |
| --- | --- |
| `runtime.input()` | Read the configured runtime input. |
| `runtime.print(value)` | Emit a value through the runtime output channel. |
| `runtime.search(...)` | Execute deterministic reasoning search. |
| `runtime.simulate(...)` | Simulate a reasoning model. |
| `runtime.predict(...)` | Produce a deterministic prediction. |
| `runtime.plan(...)` | Construct an execution plan. |

The reasoning calls operate on typed `Goal`, `State`, `Constraint`,
`ReasonGraph`, and `ExecutionPlan` bindings.

## Tensor

Tensor dtypes are `bool`, `i32`, `i64`, `f32`, and `f64`; the current backend is
CPU. Major function groups are:

| Group | Functions |
| --- | --- |
| Creation | `create`, `zeros`, `ones`, `full` |
| Random | `random_uniform`, `random_normal`, `random_bernoulli`, `random_permutation` |
| Inspection | `shape`, `rank`, `size`, `dtype`, `dimension` |
| Shape/indexing | `reshape`, `flatten`, `transpose`, `squeeze`, `unsqueeze`, `concat`, `stack`, `slice`, `narrow`, `gather` |
| Binary math | `add`, `subtract`, `multiply`, `divide`, `power`, `maximum`, `minimum` |
| Comparison | `equal`, `not_equal`, `greater`, `greater_equal`, `less`, `less_equal` |
| Elementwise | `negate`, `abs`, `exp`, `log`, `sqrt`, `relu` |
| Reduction | `sum`, `mean`, `min`, `max`, `argmax`, `argmin` |
| Linear algebra | `dot`, `matmul`, `norm`, `linear` |
| Neural network | `softmax`, `conv2d`, `max_pool2d`, `avg_pool2d` |
| Autograd | `parameter`, `detach`, `requires_grad`, `grad` |
| Conversion/I/O | `cast`, `to_array`, `scalar`, `load`, `save` |

Example:

```reason
calculation Average -> float {
  let values = tensor.create([1.0, 2.0, 3.0], "f64")
  let mean = tensor.mean(values)
  result = tensor.scalar(mean)
}
```

Tensor file paths are relative to the source resource root. `tensor.load`
requires read capability; `tensor.save` requires write capability. Absolute and
root-escaping paths are rejected.

## Optimizer

Optimizer calls are pure functions that return a new, untracked Tensor. The
caller owns the state Tensor and positive integer step counter.

```text
optimizer.sgd(param, grad, lr)
optimizer.momentum_velocity(grad, velocity, momentum)
optimizer.momentum(param, grad, velocity, lr, momentum)
optimizer.adam_moment1(grad, m, beta1)
optimizer.adam_moment2(grad, v, beta2)
optimizer.adam(param, grad, m, v, step, lr, beta1, beta2, eps)
optimizer.adamw(param, grad, m, v, step, lr, beta1, beta2, eps, weight_decay)
```

All arguments are positional. There is no mutable optimizer-handle API.

## Relation

Relation functions operate on `Array<Struct>`. Field names are strings.

```text
relation.filter(rows, predicate)
relation.filter_eq(rows, field, value)
relation.filter_ne(rows, field, value)
relation.filter_gt(rows, field, value)
relation.filter_gte(rows, field, value)
relation.filter_lt(rows, field, value)
relation.filter_lte(rows, field, value)
relation.count(rows)
relation.distinct_by(rows, field)
relation.sort_by(rows, field, descending)
```

Calls are positional and return new values without mutating the input rows.

`relation.filter` evaluates a pure Boolean expression once per row. The single
unbound name used as the root of a field access binds the current row (`row`
and `candidate` are conventional names). Other names capture the current local
values, parameters, or state fields. A predicate without a field access uses
`row`. Captures are read when the filter runs, including variables updated
earlier in execution.

```reasonscript
let factor = 3
let kept = relation.filter(candidates, candidate.value % factor != 0)
factor = 5
kept = relation.filter(kept, row.value > minimum && row.value % factor != 0)
```

Predicates support arithmetic, comparisons, Boolean operators, field access,
and indexing. Calls, I/O, and mutation are rejected (`REL-PRED-002`); the result
must be Boolean (`REL-PRED-003`). Filtering scans the source once, allocates one
output vector, and retains row references in source order. A successful pruning
operation emits one `CANDIDATE_PRUNED` semantic event with the removed source
indices and before/after counts. A filter that removes no rows emits no event.
The fixed comparison functions remain available with their existing behavior.

## Array builders

Use a transient builder for bulk construction:

```reasonscript
let builder = array.builder()
while value < limit {
  builder.append(Candidate { value: value })
  value = value + 1
}
let candidates = builder.finish()
```

`append(item)` snapshots the item, matching `array.append`'s item ownership
semantics. It grows one vector with amortized constant-time append (excluding
the size of the item), and `finish()` transfers that vector without copying it.
Element types are inferred from appends and must agree. Builder aliases share
one lifetime: after any alias finishes, subsequent append/finish calls fail
with `COLL-005`. A builder is an opaque transient handle in traces; its visible
state is its length and finished status. Its finished Array is traced normally.

Ordinary `array.append` retains its existing copy semantics. Repeated full
filters still cost the sum of all scanned rows; use bulk pruning when a meaningful
new condition is learned, rather than filtering once to remove every tested row.

## Semantic reasoning events

```reasonscript
reasoning.event("HYPOTHESIS_VERIFIED", "factor", evidence)
reasoning.event("TERMINATION_INFERRED", "complete", remaining)
```

`reasoning.event(type, subject, evidence)` returns the semantic step number.
Each call is one meaningful operation, independent of loop iterations or VM
instructions. Subjects and evidence may be ordinary values, including structs.
Supported types are `REASON_STATE_CREATED`, `RU_ACTIVATED`,
`CANDIDATE_GENERATED`, `CANDIDATE_PRUNED`, `HYPOTHESIS_CREATED`,
`HYPOTHESIS_VERIFIED`, `HYPOTHESIS_REJECTED`, `EVIDENCE_ADDED`,
`STATE_TRANSITION`, `GOAL_UPDATED`, and `TERMINATION_INFERRED`.
Unknown types fail with `REASON-EVENT-001`.

The minimal API assigns monotonically increasing state revisions and leaves
`source_ru` null. Automatic pruning events use the same step sequence. Events
appear in `reasoning_trace`; `runtime_metrics` separately reports loop iterations,
semantic steps, builder appends, scanned rows, and trace bytes. Disabling trace
retains semantic counters but records no payloads. Disabling semantic events in
the runtime request returns step `0` and emits no semantic events.

Native runtime requests may independently set `context.reason_units` to `off`
(the default), `ru`, `ru_rus`, or `ru_rus_ruo`. Enabled modes expose a
`reason_structure_trace` with canonical IDs, Evidence and ReasonRelation links,
immutable RUS revisions, and RUO lifecycle bindings. `runtime_metrics` includes
the corresponding counts, serialized allocation estimates, VM-instructions per
RU, and SHA-256 sequence/graph hashes. Turning semantic event tracing off does
not disable this explicit structure projection.

Executable Reason Units are independently controlled by
`context.executable_reason_units`: `off` (default), `count`, or `full`. `count`
uses the production-oriented fast path: it retains counters, active lifecycle
state, and rolling SHA-256 hashes without retaining RU, Evidence, Relation,
sequence, or lifecycle payloads. `full` retains those payloads for debugging
and structural inspection. Count-mode canonical JSON and semantic signatures
are streamed directly into the SHA-256 v1 contract; Count and Full therefore
produce identical sequence and lifecycle hashes without constructing the
intermediate signature or RU-ID strings in the Count hot path.
Subject and input values are canonicalized once into an inline fragment and
reused for both v1 signature and sequence positions; fragments larger than 128
bytes use a bounded fallback allocation. The specialized encoder covers JSON
numbers, strings, arrays, and objects without generic serializer calls.
`ReasonStructure` creates and activates native units before candidate predicate
evaluation, then verifies or rejects and completes them afterward. Explicit
`reasoning.event` calls remain compatible through synthetic units marked
`legacy_reasoning_event`. Full mode exposes `reason_unit_trace`; count mode
retains lifecycle, kind, Evidence, source, RUVMR, and deterministic hash metrics
without returning unit payloads. Invalid lifecycle transitions report
`RU-LIFECYCLE-001`.

### Causal relation evaluation

Native runtime requests may set `context.causal_evaluation` to `off` (the
default), `dependency`, `counterfactual`, or `full`. `causal_observations`
declare each RU's produced, required, alternative-required, and blocking
Evidence references. Direct dependencies are indexed by Evidence rather than
found by pairwise RU scans. Counterfactual mode suppresses the source RU's
Evidence and evaluates the same deterministic requirement rules again.

The runtime returns `metadata.causal_trace` with structured relations,
counterfactual results, metrics, diagnostics, and `causal_relation_hash`.
`CAUSES` requires both an Evidence dependency and counterfactual necessity;
execution order alone produces only `TEMPORAL`. `PREVENTS` is confirmed when
suppressing blocking Evidence makes the target succeed. Traversal defaults to
depth 8 and counterfactual evaluation to 32 runs, configurable through
`max_causal_depth` and `max_counterfactual_runs`. Bounds report
`CAUSAL-CYCLE-001` and `CAUSAL-BUDGET-001` without unbounded traversal.

`context.causal_observation_source` selects `external` (the compatible
default), `native`, or `merge`. Native mode projects observations directly
from typed Executable RU, Evidence, and ReasonRelation data after execution;
it does not deserialize `reason_unit_trace`. It requires
`executable_reason_units: "full"`. Runtime `relation.filter` records candidate
Evidence and a `REQUIRES` edge from each verification RU, allowing the bridge
to produce native dependencies without hand-written `causal_observations`.
`metadata.causal_bridge` reports the projected observations, deterministic
SHA-256 observation hash, diagnostics, coverage, and separately timed bridge
cost. This remains Evidence-level counterfactual evaluation, not VM replay.

### Native state causality

`context.state_causality` is `off` by default. `trace` records deterministic
state transitions; `full` also adds `CAUSES_STATE_CHANGE`, `ENABLES`, and
`TERMINATES` relations to `metadata.causal_trace`. Both enabled modes require
`executable_reason_units: "full"` so every transition has a native source RU.

Transitions are produced by the runtime reasoning state described below, never
assembled by callers. Empty diffs are omitted and rejected verification does not
create a factor-confirmed state change. `metadata.state_causality` contains
monotonic revisions, before/after values, Evidence provenance, coverage metrics,
separately measured runtime cost, and a deterministic `state_transition_hash`.
Relation provenance carries `state_revision_before`, `state_revision_after`, and
`changed_fields`. This is observed state causality, not state-level VM
counterfactual replay.

### Runtime reasoning state (Lightweight RUS)

Lightweight RUS R4 is merged to `main` and is the canonical reasoning-state runtime. It is an experimental but
integrated capability: `context.reasoning_state` and `context.state_causality` remain `off` by default, and
their semantics, artifacts, and hashes are a stable contract.

`context.reasoning_state` is `off` (default) or `lightweight`; any enabled
`state_causality` mode turns it on automatically. Both require
`executable_reason_units: "full"` (`RUS-005` otherwise). The runtime owns five
fields: `remaining`, `search_bound`, `current_candidate`,
`active_constraint_count`, and `goal_status` (`ACTIVE`, `REACHED`, `FAILED`,
`INSUFFICIENT`). State starts at revision 0 and only an update that changes a
value increments the revision; a multi-field update is one atomic transition
and a no-op update creates nothing. `metadata.reasoning_state` reports the final
state, its canonical SHA-256 `hash`, the `initial_hash`, update/no-op/changed-field
metrics, `reasoning_state_runtime_ns`, and `RUS-001`..`RUS-005` diagnostics.

The reasoning state is held in a typed, allocation-free form while the program
runs; transition IDs, before/after JSON, and relation provenance are built when
the response is constructed. `runtime_execution_ns` therefore excludes that work,
which is reported separately as `state_hash_ns`,
`state_transition_materialization_ns`, `provenance_materialization_ns`, and
`transition_hash_ns`.

State changes when an Executable RU completes, keyed by its operation, and the
transition's `source_ru` and `evidence_refs` are that RU and the Evidence it just
produced:

| RU operation (event / native) | State effect |
| --- | --- |
| `REASON_STATE_CREATED` (subject = target `n`) | initialize `remaining=n`, `search_bound=isqrt(n)`, `goal_status=ACTIVE` (revision 0, no transition; refused with `RUS-004` after any transition) |
| `HYPOTHESIS_CREATED`, `CANDIDATE_GENERATED`, native `CANDIDATE_ADOPTED` | `current_candidate = subject` |
| `HYPOTHESIS_VERIFIED` (subject = factor `f`) | `remaining = remaining / f`, `search_bound = isqrt(remaining)` in one transition; only after initialization, and `f` must divide `remaining` (`RUS-003`, no update, otherwise) |
| `EVIDENCE_ADDED`, native verified `CANDIDATE_PREDICATE` | `active_constraint_count += 1` |
| `GOAL_UPDATED`, `TERMINATION_INFERRED`, native `FILTER_GOAL` | `goal_status = REACHED` |

`relation.filter` emits these RUs natively; a factorization program only
reports semantic events with `reasoning.event`, and the runtime derives
`remaining`, `search_bound`, revisions, transitions, and relations itself. For
`n = 77` that yields `current_candidate → 7`, then one transition
`remaining 77 → 11, search_bound 8 → 3` sourced from the verification RU and its
`FACTOR_CONFIRMED` Evidence, which `ENABLES` the goal-evaluation RU, whose
`goal_status ACTIVE → REACHED` transition `TERMINATES` the termination check.

These new collection and event APIs execute in the native Rust host. The Python
interpreters retain their earlier reference API surface.

## String

```text
string.concat(left, right)
string.join(separator, values)
string.length(value)
string.from_int(value)
string.from_float(value)
string.slice(value, start, end)
```

String calls are pure and positional.

## Console & Standard Output (標準出力 API)

ReasonScript provides native standard output APIs independent of any JavaScript or host environment. JavaScript runtime APIs such as `Js.log` are strictly unsupported and rejected with diagnostic `NAM-2004`.

ReasonScript はホスト環境に依存しないネイティブな標準出力 API を提供します。`Js.log` 等の JavaScript 固有 API はサポートされておらず、使用時は `NAM-2004` エラーとなります。

### APIs

| API | Stream | Description (English) | 説明 (日本語) |
| --- | --- | --- | --- |
| `print(value, ...)` | `stdout` | Convenience output function | 初心者向けの簡易標準出力 API |
| `Console.log(value, ...)` | `stdout` | Standard informational log message | 標準情報ログ出力 |
| `Console.info(value, ...)` | `stdout` | Informational message | 通知・情報メッセージ出力 |
| `Console.warn(value, ...)` | `stderr` | Warning diagnostic message | 警告メッセージ出力 |
| `Console.error(value, ...)` | `stderr` | Error diagnostic message | エラーメッセージ出力 |

### Stringification & Determinism (決定論的文字列化)

Values passed to standard output APIs are deterministically formatted across both Python reference and Rust production runtimes:
- `Null`: `"null"`
- `Bool`: `"true"` or `"false"`
- `Int`: decimal integer format (e.g. `42`)
- `Float`: floating-point representation with decimal point (e.g. `3.14`, `1.0`)
- `String`: raw string without surrounding quotes
- `Array`: comma-separated items in brackets (e.g. `[1, 2, 3]`)
- `Struct`: alphabetically sorted keys in braces (e.g. `{a: 1, b: 2}`)
- `Enum`: `EnumName.VariantName`
- `Optional`: `Some(...)` or `None`

Multiple arguments are joined with a space and ended with a newline (`\n`).

## Vision and ReasonUnit Objects

`vision.infer` and `vision.build_ruo` execute in the native host and can produce
Tensor and ReasonUnit Object resources. `ruo.*` provides typed, opaque access
to ReasonUnit Objects, including identity/metadata queries and snapshot-based
transactions. See [ReasonUnit Objects](reasonunit-object.md) for bindings,
capabilities, and CLI examples.

## Discovering exact contracts

```sh
reason tensor-manifest --json
reason runtime-manifest --json
reason help
```

Prefer these machine-readable commands when generating code or validating an
integration.
