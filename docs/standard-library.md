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
