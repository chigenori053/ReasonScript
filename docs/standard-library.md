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

`relation.filter` and `relation.count` also accept a lazy candidate space (next
section). Over a candidate space the row binding is the candidate value itself
(an `int`), the filter is lowered to a symbolic constraint instead of a scan,
and `relation.count` answers only when it can be computed symbolically.

## Candidate spaces

A candidate space is a lazy, symbolic search space: a domain, a generation
rule, and an ordered set of constraints. Candidates are produced one at a time
by `next`, checked against the constraints at generation time, and never
materialized unless asked. Creating a space and adding constraints is O(1) /
O(constraints) work whatever the size of the domain.

```text
candidate_space.range(lower, upper)              // every int in [lower, upper]
candidate_space.wheel6(lower, upper)             // 6k-1 and 6k+1 in [lower, upper]
candidate_space.isqrt(n)                         // exact floor(sqrt(n)), for domain bounds
candidate_space.is_exhausted(space) -> bool      // looks ahead for the next accepted candidate
candidate_space.next(space) -> int               // the next accepted candidate (CS-003 when exhausted)
candidate_space.exclude_multiples_of(space, m)   // new space with `row % m != 0`
relation.filter(space, predicate)                // new space with the predicate as a constraint
relation.count(space) -> int                     // remaining candidates, symbolic only
candidate_space.reset(space)                     // new space with the cursor at the start
candidate_space.materialize(space) -> [int]      // every accepted value of the domain (explicit scan)
```

```reasonscript
let space = candidate_space.wheel6(5, candidate_space.isqrt(remaining))
while !candidate_space.is_exhausted(space) {
  let c = candidate_space.next(space)
  if remaining % c == 0 {
    remaining = int(remaining / c)
    let factor = c
    space = relation.filter(space, row % factor != 0)   // evidence -> constraint, no scan
  }
}
```

Constraints a filter can express symbolically are comparisons of the row (or
of `row % m`) against an `int` literal, a captured local, or a captured
`state.field`, combined with `&&`, `||` and `!` (`row == 7`, `row > limit`,
`row % factor != 0`, `!(row % 5 == 0)`). Ordering constraints fold into the
domain bounds; a predicate outside this set fails with `CS-PRED-001`
(materialize first and filter the array). Repeated constraints are added once,
and `a && b` is stored as two constraints in canonical order (bounds, equality,
modulo, logical trees), so the order in which evidence arrives never changes
the candidate sequence.

`next` and `is_exhausted` advance the cursor of the shared handle; a constraint
addition or `reset` returns a new handle and leaves the original unchanged.
Adding a constraint after `is_exhausted` looked ahead re-checks the pending
candidate against the new constraint; already returned candidates are never
revisited, and the cursor never moves backwards. `relation.count` over a space
with stored constraints fails with `CS-COUNT-001` rather than scanning.

The runtime emits `CANDIDATE_SPACE_CREATED` per space, `CONSTRAINT_ADDED` per
filter or exclusion call, and `CANDIDATE_SPACE_EXHAUSTED` once per space, and
counts per-candidate work in `runtime_metrics` (`candidate_space_estimated_size`,
`candidate_generated_count`, `candidate_skipped_count`,
`candidate_symbolically_excluded_count`, `candidate_materialized_count`,
`candidate_constraint_count`, `candidate_constraint_eval_count`,
`candidate_space_next_count`). In traces a space is an opaque handle showing
its domain, generator, constraints and cursor. Candidate spaces execute only
on the native runtime.

`context.constraint_fusion` -- `"off"` (default), `"always"`, or
`"adaptive"` (a plain boolean is also accepted for backward
compatibility: `true` = `"always"`, `false` = `"off"`) -- folds a prime
`NotDivisibleBy(p)` constraint directly into the space's generator (an
LCM-based wheel expansion, budgeted at a 30,030 modulus) instead of
storing it as a residual constraint evaluated per candidate, eliminating
per-candidate constraint evaluation for the primes it can absorb. This
changes only the internal representation -- results, hypothesis
sequences, and candidate order are unchanged (`relation.filter`/
`exclude_multiples_of` behave identically either way). It reduces
`candidate_constraint_eval_count`, but the one-time cost of rebuilding
the generator each time a new prime is folded in is not free: for
problems with few candidates it can make a program slower than fusion
off, not faster, unless the search space is large enough to amortize it.
`"always"` folds in every prime the budget allows; `"adaptive"` first
estimates, in O(1) with no residue scan, whether a given fusion is
likely to pay off (a candidate/constraint-evaluation benefit against the
generator's rebuild cost) and leaves the constraint residual when it
does not expect it to -- meaningfully safer than `"always"` in most
cases, though the estimate can still be misled when a program stops
generating candidates on its own (a shrinking loop variable, invisible
to the candidate space) well before the space's own domain bound.
Fusion always falls back silently to a residual constraint above the
modulus budget, on integer overflow, or (`"adaptive"` only) when the
cost estimate says it would not be worth it (`fusion_fallback_count`,
`fusion_rejected_cost_count`).

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
`STATE_TRANSITION`, `GOAL_UPDATED`, `TERMINATION_INFERRED`,
`CANDIDATE_SPACE_CREATED`, `CONSTRAINT_ADDED`, `CANDIDATE_SKIPPED`, and
`CANDIDATE_SPACE_EXHAUSTED`. Unknown types fail with `REASON-EVENT-001`.

The minimal API assigns monotonically increasing state revisions and leaves
`source_ru` null. Automatic pruning events use the same step sequence. Events
appear in `reasoning_trace`; `runtime_metrics` separately reports loop iterations,
semantic steps, builder appends, scanned rows, trace bytes, and the native
counters listed in the CLI reference (`vm_instruction_count`,
`reasoning_event_type_counts`, `hypothesis_test_count`,
`candidate_pruned_count`, ...).

Events are processed in one of three modes (`--reasoning-events`, or
`context.reasoning.event_mode` in the runtime request): `off` returns step `0`
and records nothing; `count` assigns steps and keeps per-type counters without
building an event object; `full` also materializes each event into
`reasoning_trace`. The default is `full` when a trace is enabled and `count`
otherwise, so disabling trace retains the semantic counters but records no
payloads. Disabling semantic events in the runtime request is the same as
`off`.

`relation.filter` predicates of the form `row.field <op> value`,
`row.field % m <op> value`, and their `&&`/`||`/`!` combinations, as well as
`relation.count`, execute on a native Fast Path that skips generic expression
dispatch. Results, events, counters, and diagnostics are identical to the
Generic Path; `runtime_metrics.fast_path_count` reports how often it was taken.

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
