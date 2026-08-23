# ReasonScript Agent Development Protocol

This repository follows `reasonscript-agent-protocol/1.0` for coding-agent work.

## Development Workflow

Agents execute phases in this order:

1. Specification
2. Implementation
3. Validation
4. Artifact verification
5. Golden tests
6. Completion report

Task states are monotonic:

`DRAFT -> IN_PROGRESS -> IMPLEMENTED -> VALIDATED -> COMPLETED`

`REJECTED` is terminal and is used only when the task cannot be completed under the accepted scope.

## Required Commands

The canonical entry point for repository validation is:

```sh
reason ci
```

Individual commands remain available as implementation-level interfaces for diagnosis, debugging, and incremental development:

```sh
reason workspace
reason check
reason analyze
reason run
reason artifacts
reason validate-artifacts
reason golden
reason agent-protocol
reason agent-report
```

Optional commands:

```sh
reason summary
reason manifest
reason index
reason export
```

## Validation Sequence

Every development task must run:

1. Workspace validation
2. Diagnostics validation
3. Artifact validation
4. Golden tests

A task may not be marked `VALIDATED` unless all required validations pass.

## Artifact Policy

Generated artifacts must not be edited manually. Regenerate them through official `reason` commands only.

Generated artifacts must conform to:

- `reasonscript-artifacts/1.0`
- `reasonscript-diagnostics/1.0`

## Golden Policy

Golden baselines may be updated only when:

- a specification changes,
- an intentional behavior change is implemented, or
- compatibility policy permits the update.

Golden baseline updates require a matching specification or changelog update. Do not update golden baselines automatically after validation failure.

## Completion Criteria

A task is complete only when:

- the implementation matches the task specification,
- required validation commands pass,
- generated artifacts validate successfully,
- golden tests pass,
- a completion report records results and remaining work.

## Reporting Format

Canonical machine-readable report:

```json
{
  "version": "1.0",
  "task": "Phase 7.5",
  "status": "VALIDATED",
  "tests_passed": 39,
  "artifacts_generated": true
}
```

The canonical report is generated as `agent_report.json`.

Completion reports must include:

- Completion Summary
- Implemented Features
- Validation Results
- Generated Artifacts
- Compatibility Notes
- Remaining Work

## Modernization Plan — Phase 0 Baseline Tooling

A modernization plan (language-spec fixes, a Rust computation runtime
migration, and Tensor Logic–style IR optimization) was proposed for this
repository. Its Phase 0 ("Baselineと契約凍結") calls for freezing the
Tensor Standard Functions contract surface and introducing a benchmark
baseline before any runtime rewrite begins. That baseline tooling has been
implemented:

- `reason tensor-manifest [--json] [--out DIR] [--check]` — emits the full
  argument/return/diagnostic contract of every `tensor.*` function as
  `reasonscript-tensor-function-manifest/1.0` JSON. `--check` compares the
  live contract set against the committed baseline at
  `docs/reports/tensor_function_manifest.json` and exits non-zero on drift.
  This baseline is also enforced by
  `tensor_standard_functions_tests/test_tensor_function_manifest.py`.
- `scripts/benchmark_tensor.py` (`make benchmark-tensor`) — measures
  per-call latency of the existing Python Tensor runtime at the
  micro/operator tier (cast/dispatch, elementwise, reduction, matmul,
  softmax, gather), producing `reasonscript-tensor-benchmark/1.0` JSON.

Phase 1 ("即時不具合・性能修正") has also been partially applied, scoped to
what's safe without a breaking syntax change:

- **L-004** (`float(x)` / `int(x)`): added as builtin scalar-cast calls.
  Recognized in `_expression_type` (`frontend/language_surface/validation.py`,
  `CAST-001`/`CAST-002` diagnostics) and evaluated in both the runtime
  interpreter (`frontend/integrated_computation_runtime.py`, `RT-CALL-005`)
  and compile-time constant folding (`frontend/language_surface/integration.py`).
  `int(x)` truncates toward zero (Python's native `int()` semantics) — that
  is the "明示された丸め規則" this repository has adopted. A user-declared
  `fn float(...)`/`fn int(...)` shadows the builtin, so this is additive
  only.
- **L-006 (partial)**: `/` was already true-division at runtime (Python's
  `/` operator), but the static type checker returned `Int` for
  `Int / Int`, contradicting the actual Float result — a real type/value
  mismatch bug. Fixed in `validation.py`'s `BinaryExpressionNode` handling:
  `/` is now always typed `Float`, regardless of operand types. `%` was
  already implemented and already matches `//`'s floor semantics (Python's
  `%`), so no change was needed there.
- **Evaluation no-grad** (section 11 item 3): added `TensorRuntime.no_grad()`
  (`frontend/tensor/runtime.py`), a context manager that suppresses
  autograd tape recording for its duration, even for `Parameter` inputs.
  Note the existing design already only records a tape node when an input
  is grad-tracked (`_record_autograd`), so most non-training evaluation
  already paid zero autograd overhead before this; `no_grad()` covers the
  remaining case of computing with Parameters without wanting gradients.

**Explicitly out of scope for this increment** (do not assume these are
done): the new `reason-computation-ir/0.1` IR, any Rust crate beyond the
runtimes that already exist in this repository (`RuntimeReal`,
`RuntimeComplex`, `HybridRuntime`, etc.), `Parameter<T, Shape>` /
`TensorArray<T, S>` types as first-class generic types, `Unknown` →
`TypeVar`/`Any`/`ErrorType` splitting, and introducing `//` as an
integer-division operator (`//` is currently the ReasonScript
line-comment token — see `_strip_line_comment` in
`frontend/language_surface/parser.py` — so adding it as an operator would
silently break every existing comment; this needs a dedicated
lexer/parser design pass, e.g. picking a different token or a comment
syntax migration, not an incidental change). A `DistanceDecay`-style
relation-matrix optimization target does not exist anywhere in this
repository, so that specific Phase 1 item does not apply here. There is
no `with` statement in the language surface yet, so `with tensor.no_grad
{ ... }` (section 5.4 syntax) is not available — `no_grad()` above is a
Python-level API only, reachable from evaluator code, not from `.rsn`
source.

## Modernization Plan — Phase 2 Computation IR

Phase 2 ("Computation IR") from the modernization plan has been
implemented, scoped to a Python-only IR and interpreter (no Rust yet,
per the plan's own Phase 3+ split):

- `frontend/computation_ir/schema.py`: `reason-computation-ir/0.1`
  constants, distinct from the pre-existing `reason-ir/0.1`
  (state/goal/transition/constraint IR).
- `frontend/computation_ir/lowering.py`: `lower_program()` lowers AST
  calculations and functions into basic-block Functions (Jump/Branch/
  Return/Result/Trap terminators), with an op-tagged expression tree and
  `source_span` preserved per node from the AST's `_source_location`.
  Scope is bounded to exactly what `frontend.integrated_computation_runtime`
  (the pre-existing AST evaluator) supports — pattern matching,
  Optional/Some, map/set literals, vision/ruo calls, reason_object graph
  queries, and `runtime.search/simulate/predict/plan` are out of scope
  and raise `LoweringError` rather than being silently mishandled (that
  AST evaluator doesn't support them either, so there was no oracle to
  lower them against).
- `frontend/computation_ir/interpreter.py`: `interpret_program()` — the
  Phase 2 "一時的なPython IR interpreter", walking blocks and executing
  instructions/terminators. Reuses `TensorRuntime`, `VisionRuntimeBridge`,
  `IntegratedRuntimeError`, `RuntimeStruct`, and `_index_value` directly
  from the AST evaluator rather than re-implementing their semantics, to
  avoid two copies drifting apart.
- `frontend/computation_ir/validation.py`: `validate_program()` — the
  Phase 2 "schema validation" item. Handwritten (not `jsonschema`-based,
  matching the rest of the codebase's validators): checks every
  jump/branch target resolves, every block is reachable from
  `entry_block`, and every instruction/terminator/expression node uses a
  known `op` tag.
- `frontend/computation_ir/differential.py` +
  `computation_ir_tests/test_computation_ir_differential.py`: the Phase 2
  gate — "Python AST/IR evaluatorが同一結果". `assert_same_outcome(source)`
  runs a program through both evaluators and fails loudly on any
  divergence in `calculation_results` or in which
  `IntegratedRuntimeError`/`LoopLimitError` code was raised. This harness
  caught a real lowering bug (an `elif`+`else` chain leaving one CFG
  block unreachable/unterminated) before it shipped.
- `reason computation-ir [--json] [--validate] <file.rsn>` (`toolchain/computation_ir_cmd.py`)
  lowers a `.rsn` file to IR JSON, or just validates it.

Known scope limits, not bugs: (1) a `calculation`'s `result` must be a
plain, structurally-comparable value for the differential harness —
comparing a raw `Tensor` handle across the AST run's and IR run's
*separate* `TensorRuntime` instances would spuriously "disagree" by
Python object identity even when semantically equal, so test cases
convert with `tensor.to_array`/`tensor.scalar` first. (2) The interpreter
does not reproduce `runtime.trace`/`loop_trace` entries (it passes `[]`
for loop_trace) — differential testing compares `calculation_results`
and error codes, not trace/performance metadata.

**Not done in this phase** (Phase 3+, deferred): no Rust IR decoder or
Rust primitive-execution CLI: this interpreter is Python-only by design
(the plan's own "この段階ではTensor kernelを移植しない" principle for
Phase 2/the bootstrapping steps in section 21). No Rust computation
runtime crates exist yet.

## Modernization Plan — Phase 3 Rust VM Skeleton

Phase 3 ("Rust VM skeleton") has been implemented as a new, independent
Cargo workspace at `ReasonComputationRuntime/`, following the plan's own
"採用しない設計" list (section 19: no Tensor-in-`RuntimeReal`, no
per-operation subprocess) and its full target crate layout (section 8) —
only the crates Phase 3 actually needs exist yet:

```
ReasonComputationRuntime/
  crates/
    computation-ir/   -- runtime-types + IR decoder + VM, combined for
                          this phase (folds the plan's separate
                          "runtime-types"/"computation-ir"/"computation-vm"
                          crates into one lib crate; may be split later
                          if/when Tensor/autograd/relation-engine crates
                          are added in later phases)
    runtime-cli/       -- the "Rust CLI" bullet: `reason-computation-runtime`
```

- `computation-ir::ir`: serde-decodes `reason-computation-ir/0.1` JSON
  (the exact format `frontend.computation_ir.lowering` emits) into typed
  Rust structs/enums.
- `computation-ir::value::Value`: `Null | Bool | Int(i64) | Float(f64) |
  String | Array | Struct` (no `Tensor`/`Function`/`OptimizerState` yet —
  those are Phase 4+). `Array`/`Struct` use `Rc<RefCell<..>>`, not
  by-value storage, because ReasonScript arrays/structs have
  reference/aliasing semantics on the Python side (`values[0] = 99`
  mutates every binding aliasing that array) that by-value Rust storage
  would silently break.
- `computation-ir::vm::Vm`: walks blocks/terminators exactly like
  `frontend/computation_ir/interpreter.py` (same visit-count loop guard,
  same `RT-*`/`RT-ARITH-001`/`RT-INDEX-*`/`RT-CALL-*` error codes,
  Python-matching floor-mod for `%` since Rust's `%` truncates toward
  zero instead). `call_tensor`/`call_vision` are recognized but return
  `RT-UNSUPPORTED-001` rather than executing or panicking — Tensor/vision
  execution is genuinely Phase 4+ scope.
- `reason-computation-runtime` binary: reads a `reason-computation-ir/0.1`
  document (path arg or stdin) and prints
  `{"ok": true, "calculation_results": {...}}` or
  `{"ok": false, "error_code": "...", "error_message": "..."}` — a
  deliberately simple JSON shape (not the full
  `reasonscript-integrated-runtime/0.1` envelope) so it's trivial for the
  Python side to decode and diff against.
- `frontend/computation_ir/rust_bridge.py` +
  `computation_ir_tests/test_computation_ir_rust_parity.py`: the Phase 3
  gate itself — "Tensorなしcalculationのpython/Rust一致". Builds/finds the
  compiled binary (candidate paths under `ReasonComputationRuntime/target/`,
  mirroring `toolchain.native_runtime`'s pattern for the unrelated native
  ReasonUnit Runtime binary) and asserts the Rust CLI's output matches
  `interpret_program`'s for the same lowered IR, on both `calculation_results`
  and error codes, for representative arithmetic/control-flow/array/struct/
  cast programs, plus one intentionally-asymmetric case proving Tensor
  calls are cleanly rejected (`RT-UNSUPPORTED-001`) rather than silently
  wrong. The whole test module skips (not fails) if the binary hasn't been
  built. `ReasonComputationRuntime` was added to `scripts/test_platform.py`'s
  `RUST_CRATES`/`RUST_TEST_CRATES`, so `python3 scripts/test_platform.py test`
  builds and `cargo test`s it before the Python parity tests run, matching
  how the pre-existing Rust crates are wired into the test platform.
- 6 Rust-native unit tests in `computation-ir` (`cargo test`), covering
  Python-floor-mod parity, Divide-always-Float, zero-division error code,
  the "calculation with no result" outcome, Tensor-call rejection, and
  out-of-range index error code.

**Not done in this phase** (Phase 4+): Tensor storage/handle/view,
binary/reduce/matmul/gather/softmax kernels, `.rstensor` I/O, RNG,
autograd/optimizer, IR optimization passes, the relation engine, and
GPU/BLAS backends all remain Python-only for now, exactly as the plan's
own phase ordering intends.

## Modernization Plan — Phase 4 Rust Tensor Forward

Phase 4 ("Rust Tensor forward") has been implemented as a new
`reasonscript-tensor-core` crate in `ReasonComputationRuntime/`, wired
into `computation-ir`'s VM so `call_tensor` executes for real instead of
always returning `RT-UNSUPPORTED-001`:

- `crates/tensor-core/src/{dtype,shape,store,ops,rng,io,json}.rs`:
  Tensor storage/handle (`tensor_%04d` ids, matching Python's naming),
  dtype system (`bool|i32|i64|f32|f64`, computed internally as `f64`
  regardless of declared dtype — the plan's "compat-reference" numeric
  mode, section 10), dense CPU reference ops, the SHA-256-counter RNG,
  and `.rstensor` encode/decode.
- `crates/computation-ir/src/tensor_dispatch.rs`: maps `tensor.*`
  function ids to `tensor-core` calls, positional-argument-for-argument
  matching each Python method's signature and defaults (ReasonScript
  Tensor calls are always positional — no keyword-argument syntax in
  `.rsn` source).

**Implemented (~50 of the 65 Tensor Standard Functions)**: `create`,
`zeros`, `ones`, `full`, `shape`, `rank`, `size`, `dtype`, `dimension`,
`reshape`, `flatten`, `transpose`, `squeeze`, `unsqueeze`, the 7 broadcast
binary ops (`add`/`subtract`/`multiply`/`divide`/`power`/`maximum`/`minimum`),
the 6 comparisons, the 5 unary elementwise ops (`negate`/`abs`/`exp`/`log`/`sqrt`),
`sum`/`mean`/`min`/`max`/`argmax`/`argmin`, `dot`/`matmul`/`norm`, `cast`,
`to_array`/`scalar`, the 4 `random_*` RNG functions, and `.rstensor`
`load`/`save`.

**Deliberately NOT implemented** (return `RT-UNSUPPORTED-001`, never a
wrong answer or a panic — see `tensor_dispatch.rs`'s module doc): `slice`,
`narrow`, `gather`, `concat`, `stack` (indexing-heavy shape ops);
`relu`/`softmax`/`linear`/`conv2d`/`max_pool2d`/`avg_pool2d` (neural-net
inference ops); `parameter`/`detach`/`requires_grad`/`grad` (autograd,
Phase 5 scope). The full 65-function Tensor Standard Functions contract
is frozen and diffable via `reason tensor-manifest` (Phase 0 tooling) —
cross-reference it against this list to see exactly what's left.

**Verified, not just implemented**:
- RNG matches Python byte-for-byte: `random_unit("uniform", 42, 0, 0)`
  and `..., 0, 1)` are golden-value-tested against
  `frontend.tensor.runtime._random_unit`'s actual output
  (`crates/tensor-core/src/rng.rs`'s unit tests).
- `.rstensor` cross-language interop is exercised in both directions
  (`computation_ir_tests/test_computation_ir_tensor_parity.py`'s
  `test_rust_writes_python_reads` / `test_python_writes_rust_reads`):
  Rust writes a file, Python's `TensorRuntime.load` reads it correctly
  (and vice versa) — not just "each side can read its own files."
  Header JSON is read generically on both sides (any valid JSON with the
  right keys), so this doesn't require byte-identical `json.dumps`
  formatting between the two languages.
- A real numeric divergence was found and fixed during this work: Python
  `float / 0.0` raises `ZeroDivisionError` at the moment of computation
  (caught generically by `TensorRuntime.call()` and normalized to
  `TensorError("TSF-012", ...)`), whereas Rust's IEEE-754 `f64` division
  silently produces `inf`. `tensor_dispatch.rs`'s `divide()` pre-checks
  for a zero divisor and reports the same `TSF-012` rather than letting
  Rust compute `inf` and have the finite-value check reject it under a
  different code (`TSF-010`) — a genuine cross-language semantic gap,
  not a hypothetical one.
- The differential harness
  (`computation_ir_tests/test_computation_ir_tensor_parity.py`, 16 tests)
  covers creation/inspection, shape ops, broadcast/comparison/unary
  elementwise, axis+keep_dims reductions, argmax/argmin, dot/matmul/norm,
  cast, all 4 RNG functions, and error-code parity for division-by-zero,
  broadcast-shape-mismatch, and matmul-dimension-mismatch — plus the
  `.rstensor` round trips above. All pass, including exact RNG output
  equality (not just "both succeeded").

**Known simplifications** (documented, not silent): resource-policy
ceilings (`max_live_tensors`, `max_elements`, `max_tensor_bytes`, ...)
aren't enforced in Rust yet — shape/finiteness *correctness* is, the
resource *policy* ceiling is follow-up scope. Non-finite values are
rejected with a single `TSF-010` regardless of which operation produced
them (Python distinguishes `TSF-010` at creation from `TSF-012`
mid-computation in the general case; only the `divide`-by-zero case above
was worth reproducing exactly, since it's the one path a normal program
is likely to hit). `.rstensor` path resolution doesn't yet replicate
Python's `_resolve_tensor_path` sandboxing (absolute/traversal rejection,
`resource_root` confinement, `.rstensor`-suffix requirement) — it's a
plain `std::fs` read/write relative to the CLI's working directory.

## Modernization Plan — Phase 5 Rust Autograd

Phase 5 ("Rust Autograd・Optimizer") has been implemented **for its
autograd half only** — see "Optimizers: not implemented" below for why
the other half is a separate, unresolved scope question rather than an
oversight.

- `crates/tensor-core/src/autograd.rs`: `Autograd` (tape + `requires_grad`
  set) and `GradOp` (one recorded forward op, enough to compute its VJP —
  an explicit enum per op *kind*, rather than replaying a generic
  argument list the way Python's `_GradNode`/`_vjp` do; each variant maps
  1:1 to one of `_vjp`'s `name in {...}` branches). `TensorStore::insert_with_grad`
  tapes an op (mirroring `_record_autograd`'s "only if an input is
  already tracked, and only for f32/f64 output" rule) alongside the
  normal `insert`.
- VJPs implemented, matching `_vjp` exactly: the 7 broadcast binary ops,
  the 5 differentiable unary ops (`negate`/`abs`/`exp`/`log`/`sqrt`),
  `reshape`/`flatten`/`squeeze`/`unsqueeze`/`cast` (all share Python's
  "gradient passes through unchanged" `ShapePassthrough` treatment),
  `transpose`, `sum`/`mean` (axis + keep_dims aware), `min`/`max`
  (including Python's first-occurrence tie-breaking on the argmax/argmin
  index a reduced gradient scatters back to), `matmul`, `dot`, `norm`.
  Not implemented (no forward op to attach a VJP to in the first place —
  see Phase 4's own boundary): `concat`/`stack`/`slice`/`narrow`'s VJPs,
  and `relu`/`softmax`/`linear`/`conv2d`/`max_pool2d`/`avg_pool2d`'s.
- `tensor_dispatch.rs` adds `parameter`/`detach`/`requires_grad`/`grad`
  (all four correctness-verified against Python — see below), bringing
  the implemented-Tensor-Standard-Functions count to the same ~50 as
  Phase 4 (these four were always counted in that total; Phase 4's
  writeup just deferred implementing them).
- A real bug this work uncovered and fixed: Python's `_binary()` (the
  broadcast ops) silently auto-promotes a bare scalar/array literal
  passed as either operand into an ad-hoc Tensor via `_operand()` (e.g.
  `tensor.multiply(gradients[0], 0.1)` — a raw `0.1` literal, not a
  Tensor handle). The Rust port's `binary`/`compare`/`divide` initially
  required a real `Value::Tensor` for both operands and rejected this
  with `RT-CALL-005`; `tensor_dispatch.rs`'s `operand_id()` now mirrors
  `_operand()` (auto-inserts a fresh, untracked Tensor for a bare
  literal operand) — found via `test_scalar_literal_operand_is_auto_boxed`
  after a hand-written 20-step gradient-descent program (below) failed
  before this fix.

**Verified, not just implemented**:
- `crates/tensor-core/src/autograd.rs`'s own Rust unit test
  (`multiply_add_sum_gradient_matches_finite_differences`) is the Phase 5
  gate's "finite difference" check, run standalone (no Python process
  needed): builds `loss = sum(a + a*b)` on the real tape, gets the
  gradient via `Autograd::grad`, and checks it against numerical central
  differences on the untraced forward computation (and against the
  closed-form `d(loss)/da = 1+b`, `d(loss)/db = a` directly).
- `computation_ir_tests/test_computation_ir_autograd_parity.py` (18
  tests): differential Python/Rust parity for every VJP above, plus
  `parameter`/`detach`/`requires_grad`, the scalar-auto-boxing case, and
  AD-001/AD-002/AD-003 error-code parity.
- A genuine "1/100 step loss" stand-in: a 20-iteration hand-rolled
  gradient-descent loop (`prediction = input*weight; loss =
  mean(prediction^2); weight -= 0.1*grad`, re-parameterizing via
  `detach`+`parameter` each iteration, exactly Phase 2's own
  `test_reason_training_loop_releases_each_autograd_tape` fixture)
  produces `0.8**20` to full `f64` precision in both Python and Rust —
  `test_gradient_descent_training_loop_matches`.

## Modernization Plan — Optimizer (SGD / Momentum / Adam / AdamW)

Previously "Pending — explicitly deferred as a separate scope decision"
(see git history for the original note): there was no `optimizer.*`
namespace anywhere in ReasonScript to port from or diff a Rust rewrite
against, unlike every other phase (which had an existing Python behavior
to port and differentially test against). The repository owner made the
explicit scope call to build it as new language surface + runtime,
simultaneously in Python and Rust, cross-validated against each other
and against hand-derived closed-form values instead of an existing
oracle.

**API shape** (`frontend/tensor/optimizers.py`'s docstring has the full
rationale): every `optimizer.*` function takes Tensor/scalar arguments
and returns a single new Tensor -- never a struct with multiple named
outputs. This is a deliberate consequence of a real language-surface
gap: `frontend/language_surface/validation.py`'s static type checker
only resolves `.field` member access on a `NamedTypeNode` that has a
matching `StructDeclarationNode` in scope, and there's no way to
register a synthetic one for a function's return type (the same reason
`tensor.save`'s `TensorArtifactReceipt` result can be stored but never
field-accessed today). So callers that need both an updated parameter
and updated optimizer state call multiple functions, e.g.:

```
let velocity = optimizer.momentum_velocity(grad, velocity, 0.9)
let param = optimizer.momentum(param, grad, velocity, 0.01, 0.9)
```

**Functions**: `optimizer.sgd(param, grad, lr)`,
`optimizer.momentum_velocity(grad, velocity, momentum)`,
`optimizer.momentum(param, grad, velocity, lr, momentum)`,
`optimizer.adam_moment1(grad, m, beta1)`,
`optimizer.adam_moment2(grad, v, beta2)`,
`optimizer.adam(param, grad, m, v, step, lr, beta1, beta2, eps)`,
`optimizer.adamw(param, grad, m, v, step, lr, beta1, beta2, eps,
weight_decay)` (decoupled weight decay: `param - lr*update -
lr*weight_decay*param`). `step` is a positive Int the caller increments
itself between iterations (rejected as `OPT-005` otherwise) -- there is
no implicit optimizer-owned counter.

**Deliberately separate from Tensor Standard Functions**: `optimizer.*`
is not part of the `tensor_function_manifest.json` stability contract
(`reason tensor-manifest --check` stays untouched), has its own
`OPT-001`..`OPT-005` diagnostic family, its own IR node (`call_optimizer`,
alongside `call_tensor`/`call_vision` in `frontend/computation_ir/schema.py`),
and its own dispatch on every layer: `TensorRuntime.call_optimizer`
(`frontend/tensor/runtime.py`, composed from the same `self.add`/
`self.subtract`/`self.multiply`/`self.divide`/`self.power`/`self.sqrt`
elementwise primitives `tensor.*` uses, called directly rather than
through `self.call(...)` so results are never autograd-taped -- an
optimizer step's output is a fresh, untracked Tensor, like
`tensor.detach`), the AST evaluator's `_expression`
(`frontend/integrated_computation_runtime.py`), the IR interpreter
(`frontend/computation_ir/interpreter.py`), and
`ReasonComputationRuntime/crates/computation-ir/src/optimizer_dispatch.rs`
(composed the same way, from `reasonscript_tensor_core::ops::broadcast_binary`
directly, storing results untracked via `store_insert` rather than
`store_insert_grad`). The Phase 7 IR optimizer treats `call_optimizer`
exactly like `call_tensor`: side-effect-free (so an unused step result
can be dead-code-eliminated) but never CSE-deduplicated (a step can
raise on a bad step count or shape mismatch).

**Verified**:
`computation_ir_tests/test_computation_ir_optimizer_functions.py` (14
tests) covers every function's output against a hand-derived closed-form
value, differentially across the Python interpreter and the Rust binary
(bit-exact for every single-call test); a 30-iteration Adam training
loop minimizing `(w-2.0)^2` that actually converges towards the target
(exact `assertEqual` parity is deliberately not required there --
Rust's `powf` and Python's float `**` are different libm call paths
that round differently in their last bit, and 30 iterations compound
that into a real but tiny divergence; every individual op is still
proven bit-exact elsewhere in the same file); static validation
rejecting a non-Tensor argument (`OPT-003`), wrong argument count
(`OPT-002`), and an unknown Optimizer function (`OPT-001`); the older
AST evaluator's independent `optimizer.*` dispatch branch (used when
Phase 6's Rust-first path falls back to Python); that no `optimizer.*`
name ever appears in `TensorRuntime.contracts`; and that a hand-built
IR node with too few arguments (unreachable from real `.rsn` source,
since `validate_optimizer_call` enforces the exact count before
lowering, but reachable from a raw IR document) is rejected as a normal
`OPT-002` `RuntimeError` rather than panicking (`momentum`/`adam`/
`adamw` clone specific argument positions into a reconstructed slice
for a shared sub-computation, which isn't bounds-checked on its own --
`optimizer_dispatch::call` checks the count upfront specifically so
that indexing can never run past the end).
`computation_ir_tests/test_computation_ir_optimizer.py` (the Phase 7 IR
optimizer's own suite) additionally covers `call_optimizer`'s
interaction with constant folding/DCE/CSE: an unused step is
eliminated, a used one survives optimization with an identical result,
and two structurally-identical calls are never merged. Optimizer errors
also carry `source_location` in their diagnostic (`TensorRuntime.call_optimizer`
accepts and attaches `_source_location`, mirroring `call()`) -- Rust
does not attach one, consistent with the rest of the Rust VM not having
trace/diagnostic-location parity yet (Phase 6). Named-argument syntax on
an `optimizer.*` call (unsupported -- these are positional-only) is
rejected with `OPT-002` at parse time rather than falling through to a
misleading Tensor diagnostic.

**Not implemented** (documented gaps): a stateful `optimizer.step(handle,
...)` object API (would need a new mutable-handle runtime concept
ReasonScript doesn't have), learning-rate schedulers, gradient clipping,
and per-parameter-group hyperparameters (a caller-side ReasonScript loop
over an array of parameters, calling these per-Tensor functions, covers
that today). Static shape inference (`frontend.tensor.integration.infer_tensor_shape`)
does not know about `optimizer.*` results, so a Tensor op consuming an
optimizer step's output has an "unknown" shape for compile-time
shape-mismatch checks (no different from any other function whose
return shape isn't specially inferred; runtime shape checks still
apply).

## Modernization Plan — Phase 6 Rust Default Execution

Phase 6 ("Rust主実行器: Rust default、Python fallback") is implemented in
`scripts/reason_cli.py`, the actual entry point `reason run`/`reason check`
use for calculation/Tensor programs (`_run_result`, gated by
`_requires_integrated_runtime` — note this is a *different* code path
from `toolchain/run_cmd.py`'s `reason run`, which executes the older
`reason-ir/0.1` state/goal/transition pipeline against `RuntimeReal`/
`HybridRuntime` and is untouched by this phase):

- `_try_rust_execution()`: lowers the program, resolves the compiled
  `reason-computation-runtime` binary, and runs it. Returns `None` (fall
  back to `execute_program`, unchanged below it) when: the binary isn't
  built, `lower_program` raises `LoweringError` (an unsupported language
  construct), the program touches `tensor.load`/`save` but the caller
  wasn't granted both filesystem capabilities (Rust has no equivalent
  gate to Python's `TIO-001` check, so this routes those programs to
  Python rather than silently bypassing it), or the Rust run itself
  fails for any reason (including a genuine runtime error like division
  by zero) — that last case intentionally re-derives the diagnostic via
  Python's already-tested error-handling path rather than reshaping a
  Rust `code`+`message` into Python's diagnostic dict shape here.
- On success, `result["execution_mode"] = "integrated-rust"` (vs.
  `"integrated"` for the Python path), so which engine ran is always
  visible in `reason run --json` output.
- `include_trace` (`reason run --trace` or `--json`) always uses Python:
  the Rust path returns empty `tensor_metadata`/`tensor_trace`/
  `loop_trace`/`vision_trace` (documented, not silently dropped) because
  full trace/diagnostic parity is real remaining work, not attempted in
  this phase.
- Shadow mode (`REASONSCRIPT_SHADOW_MODE=1`): after a successful Rust run,
  also runs the same program through Python and prints a mismatch
  warning to stderr (without failing the run) if `calculations` disagree
  — `_shadow_check_against_python()`. Opt-in, for validating parity on
  real programs during the migration without paying double-execution
  cost by default.
- `runtime-cli`'s `serde_json` now uses the `preserve_order` feature:
  `calculation_results` must come back in execution order (Python's
  `next(reversed(calculations.values()))` semantics for picking the
  "current" result value), and plain `serde_json::Map` is BTreeMap-backed
  and would have silently alphabetized the keys instead.

**Verified**: `runtime_completeness_tests/test_phase6_rust_default_dispatch.py`
covers the Rust-success path, the unsupported-construct fallback, the
always-Python trace path, both `tensor.load`/`save` capability-gating
cases, `_uses_tensor_io`'s detection, and a shadow-mode agreement case
(asserting `print` is never called when both engines agree). One
pre-existing test (`test_scalar_calculation_uses_integrated_runtime_without_trigger_construct`)
had hardcoded `execution_mode == "integrated"` for a plain scalar
calculation with no Tensor calls at all — now that Rust correctly
executes it too, this was updated to accept either mode (the program has
no unsupported construct, so which one runs is just "is the binary
built", not a correctness question).

**Not done in this phase** (documented gaps, not oversights): the Python
AST evaluator has NOT been removed from the "normal path" — it remains
the always-available fallback, which is exactly what "Rust default、
Python fallback" (the plan's own phrase) asks for, not a stepping stone
to deletion. Full trace/diagnostic parity (Rust producing
`tensor_trace`/`loop_trace`/`vision_trace` equivalents) is unbuilt. The
gate's "Model D batch=8" / "Transformer学習・評価・介入がRustのみで完了"
criteria are unattainable in this repository — no Transformer fixture
exists here (see the earlier Phase 4 investigation); the "Rust
default/Python fallback" *architecture* itself is what's been built and
verified instead.

## Modernization Plan — Phase 7 IR Optimization

Phase 7 ("IR最適化") is `frontend/computation_ir/optimizer.py`:
`optimize_program(document) -> document`, a pure function over
`reason-computation-ir/0.1` JSON that runs once on the Python side and
benefits both consumers of that IR (`frontend.computation_ir.interpreter`
and the Rust `reason-computation-runtime`), rather than duplicating
optimization passes in two languages.

Implements the subset of the plan's Phase 7 pipeline (section 7) that
applies to this IR's actual shape:

- **Constant folding** (`_fold_expr`): folds `binary`/`comparison`/
  `unary`/`logical` (with And/Or short-circuiting)/`call_cast` nodes whose
  operands are all `const`. A fold that would raise (division/modulo by
  zero) is deliberately left unfolded, so the runtime still raises
  RT-ARITH-001 at the correct point instead of the optimizer encoding
  "this folds to an error".
- **Dead branch elimination** (`_simplify_branches`): a `branch`
  terminator with a constant-folded condition becomes an unconditional
  `jump`.
- **Unreachable block removal**: blocks no longer reachable from
  `entry_block` after branch simplification are dropped.
- **Dead local elimination** (`_eliminate_dead_locals`): an `assign`
  whose target is never read elsewhere in the function, and whose
  expression is side-effect-free, is removed. `tensor.load`/`tensor.save`
  are always treated as impure (never eliminated even if unused);
  `call_vision`/`call_function` are conservatively always impure too (a
  user function's body may itself call `tensor.save`).
- **Local common-subexpression elimination** (`_local_cse`): within one
  straight-line block, a repeated structurally-identical pure expression
  is replaced with a reference to the local already holding its value.
  `call_tensor`/`call_vision`/`call_function`/`call_array_append` are
  never deduplicated (Tensor calls can raise; a user function can have
  side effects). A real bug was found and fixed here during development:
  the first draft's cache invalidation on reassignment was a no-op,
  which would let a self-referential assign like `i = i + 1` poison the
  cache so a *later*, syntactically identical `i + 1` (referring to the
  new value of `i`) wrongly collapsed to plain `i`. Fixed by invalidating
  any cached expression that reads a target before that target is
  reassigned, and by never caching an assign whose own expression reads
  its own target.

**NOT implemented** (documented, not silent): cross-block CSE,
loop-invariant code motion/hoisting, a Relation Matrix-style cache (no
relation engine exists in this repository to cache against), gradient
pruning as a *compile-time* IR pass (both the interpreter and the Rust VM
already only walk autograd tape nodes reachable from the requested loss
at `grad()`-call time — see `ReasonComputationRuntime/crates/tensor-core/
src/autograd.rs` — which is this codebase's existing form of "don't
generate a VJP that can't reach the loss"), liveness-driven Tensor buffer
reuse, and kernel fusion (softmax isn't implemented at all, and `matmul`
is rank-2/unbatched only, so there is nothing to fuse).

**Verified**: `computation_ir_tests/test_computation_ir_optimizer.py` (18
tests) covers constant folding (arithmetic/comparison/logical short-
circuit/cast, and that divide/modulo-by-zero are left unfolded and still
raise RT-ARITH-001), branch simplification and unreachable-block removal,
dead-local elimination (including that `tensor.save`/`tensor.load` always
survive even when unused), local CSE (including a dedicated regression
test for the self-referential-assign fix above, and a reassignment-
invalidation test), and that Tensor calls are never CSE-deduplicated.
Every test lowers a program once and differentially compares
`calculation_results`/error code across up to four runs: unoptimized
Python, optimized Python, unoptimized Rust, and optimized Rust (the Rust
comparisons run only when the binary is built, matching every other
`computation_ir_tests` parity suite) — optimization must never change
what a program computes.

**CLI**: `reason computation-ir --optimize [--json|--validate] <file.rsn>`
(`toolchain/computation_ir_cmd.py`) runs the optimizer before printing/
validating the IR. This is opt-in and inspection-only: `_try_rust_execution`/
`interpret_program`'s default execution paths (Phase 6) do NOT apply the
optimizer automatically. No before/after "cell dispatch" or "5x speedup"
benchmark was attempted: the plan's Phase 7 gate metrics ("cell dispatch
90%以上削減、現行比5倍以上") are framed around the Relation Matrix/Tensor
Logic hybrid engine described elsewhere in the plan, which (like the
Transformer/Model A-D fixtures noted under Phase 4/6) has no
implementation or fixture in this repository to benchmark against; wiring
the optimizer into the default execution path and measuring real
before/after numbers on this repo's actual programs is left as follow-up
work once that's decided, rather than reporting a fabricated speedup
figure here.

## Modernization Plan — Phase 8 Tensor Logic Hybrid (Relational Algebra Core)

Phase 8 of the plan ("relation tuple/join/projection/filter planner,
dense/sparse partition/query slicing/shared index plan") is written
around a "Reason / Routing relation" and "Relation Matrix" that live in
a companion `Transformer_Test` repository referenced in the plan's own
"関連文書" list, not in ReasonScript itself -- like the Transformer A-D
fixtures noted under Phase 4/6, that repository is not available in this
session, so the plan's gate ("対象領域でdense全走査比2倍以上") has no
target to benchmark against here. Confirmed by scope decision with the
repository owner: this phase is narrowed to the *relational algebra*
that IS groundable in ReasonScript's own language surface --
`Array<Struct>` is already a relation's tuple set -- and the dense/sparse
Tensor partitioning half stays out of scope (`tensor-core` still stores
every dtype as a dense `Vec<f64>`; a real sparse representation would be
its own large undertaking with its own scope decision, per the pattern
this plan already used for Optimizer).

**Why `join`/`project` aren't implemented**: both change a row's field
shape. ReasonScript's static type checker only resolves `.field` access
on a `NamedTypeNode` backed by a real `StructDeclarationNode` -- there is
no way to synthesize one for a join's or projection's derived field set
(the same gap `frontend/tensor/optimizers.py` documents for
`optimizer.*`, but this time there's no "return a single Tensor instead"
escape hatch: a join's or projection's output genuinely *is* a
differently-shaped row set). Fixing this needs either (1) duck-typing a
join/projection's output field set against whatever `StructDeclarationNode`
in the module's symbol table structurally matches it, or (2) new
call-site syntax naming the target struct type explicitly -- a real,
separate language-design decision this pass does not make.

**Why arbitrary predicates aren't supported**: ReasonScript has no
closures or anonymous functions (checked -- no lambda/function-value AST
node exists, and the Rust `Value` enum has no `Function` variant despite
the plan's section 8 anticipating one). A `relation.filter(rows,
predicate)` taking an arbitrary predicate is therefore not expressible.
Every filter function instead takes a field name (a required string
literal, enforced at parse time as `REL-003`) and a comparison value --
the same "literal instead of a closure" pattern `tensor.softmax(input,
axis)` already uses for its axis argument.

**Functions** (`frontend/relation/integration.py`, all type-preserving:
input and output are always the same `Array<Struct>` type, so no
synthetic struct type is ever needed): `relation.filter_eq`/`filter_ne`/
`filter_gt`/`filter_gte`/`filter_lt`/`filter_lte(rows, field, value)`,
`relation.count(rows)`, `relation.distinct_by(rows, field)` (keeps the
first occurrence per distinct field value, in source order),
`relation.sort_by(rows, field, descending)`.

**Dispatch**: a new `call_relation` IR node (`frontend/computation_ir/schema.py`),
lowered by `frontend/computation_ir/lowering.py`, and a plain
module-level `call_relation(function_id, *args)` function in
`frontend/integrated_computation_runtime.py` (not a method on any
runtime class -- unlike `TensorRuntime.call`/`call_optimizer`, every
`relation.*` function is a pure `Array<Struct>` read with no Tensor
backend, autograd, or persistent state involved). Both the AST evaluator
and the IR interpreter (which imports `call_relation` from
`integrated_computation_runtime` rather than duplicating it) dispatch
through it. Comparisons reuse the exact same operator semantics as a
plain `a < b` expression (`_COMPARISON_OPS`/`ComparisonOperator` on the
Python side, `vm::eval_comparison` reused directly -- made `pub(crate)`
for this -- on the Rust side in
`ReasonComputationRuntime/crates/computation-ir/src/relation_dispatch.rs`,
which needs no `TensorStore` at all). `relation_dispatch::call` checks
argument count upfront before any positional access, the same
panic-safety pattern `optimizer_dispatch::call` uses. The Phase 7 IR
optimizer treats `call_relation` like `call_tensor`/`call_optimizer`:
side-effect-free (an unused relation call can be dead-code-eliminated)
but never CSE-deduplicated (a comparison can raise on an incomparable
field type). `relation.*` stays fully outside the Tensor Standard
Functions contract, with its own `REL-001`..`REL-007` diagnostic family
(`reason tensor-manifest --check` untouched).

A real parity fix during development: `distinct_by`'s first draft used a
Python `set()` to track seen field values, which raises on an unhashable
field (e.g. a field that's itself an Array or Struct); the Rust side's
linear equality scan never hashes anything, so it wouldn't raise in that
case. Fixed by changing Python's `distinct_by` to also use a linear
equality scan instead of a hash set, so both sides accept exactly the
same field values. A second fix in `sort_by`'s Rust comparator: the
first draft derived a 3-way `Ordering` naively ("not less-than =>
Greater"), which reports `Greater` for two *equal* fields in both
directions -- an inconsistent comparator. Fixed by deriving `Less`/
`Equal`/`Greater` from two `<` comparisons (mirroring how Python's
`sorted()` also only ever calls `<` on the extracted keys), verified by
a dedicated stability test (`test_sort_by_is_stable_for_equal_keys`).

**Verified**: `computation_ir_tests/test_computation_ir_relation_functions.py`
(19 tests) covers every function's behavior against hand-derived
expected results, differentially across the Python interpreter and the
Rust binary; error-code parity for an unknown field (`REL-005`), an
incomparable field-type comparison (`REL-006`), a non-`Array<Struct>`
argument (`REL-004`); static validation for a non-string-literal field
argument (`REL-003`), wrong argument count (`REL-002`), an unknown
Relation function (`REL-001`), and rejected named-argument syntax;
sort stability for equal keys; and that no `relation.*` name ever
appears in `TensorRuntime.contracts`. `computation_ir_tests/test_computation_ir_optimizer.py`
additionally covers `call_relation`'s interaction with the Phase 7 IR
optimizer (unused call eliminated, used call survives optimization,
never CSE-deduplicated) -- the same coverage Phase 7's own audit added
for `call_optimizer`.

**Not implemented** (documented gaps, not oversights): `join`/`project`
(see above -- needs a real struct-type design decision first); dense/sparse
Tensor partitioning, query backward slicing, and shared index plans (need
a sparse Tensor representation `tensor-core` doesn't have); anything
tied to the plan's Transformer-specific "Reason / Routing relation" or
"Relation Matrix" framing, since no such fixture exists in this
repository to build or benchmark against.

## Modernization Plan — Phase 9 Fast Backend (Native-Fast Numeric Mode + Parallel CPU)

Phase 9's full scope ("true f32/parallel CPU/BLAS/GPU/cost model", gate
"現行比10倍以上、accuracy低下0.1pt以内") is narrowed by an explicit scope
decision after checking this environment: no GPU is present (no
`nvidia-smi`), and no system BLAS/LAPACK library was found via
`ldconfig`, so both are Pending. `crates.io` access was confirmed
working, so a pure-Rust dependency (`rayon`) was addable. The
"accuracy低下0.1pt以内" gate is (like Phase 6/7/8's benchmarks) framed
around a Model D/Transformer evaluation this repository has no fixture
for. What's implemented instead: a genuinely new second `NumericMode`
(`reasonscript-tensor-core`'s `dtype.rs`) alongside the existing,
default, completely unchanged `CompatReference` --

- `NumericMode::CompatReference` (default, selected whenever
  `REASONSCRIPT_NUMERIC_MODE` is unset or not exactly `"native-fast"`):
  identical to every prior phase's behavior. Every existing test in this
  repository runs under this mode without ever touching the new code
  paths at all.
- `NumericMode::NativeFast` (`REASONSCRIPT_NUMERIC_MODE=native-fast`,
  `runtime-cli/src/main.rs`'s `numeric_mode_from_env`, mirroring the
  `REASONSCRIPT_SHADOW_MODE` env-var precedent from Phase 6): real `f32`
  rounding, and parallel (`rayon`) execution for the highest-traffic ops.

**Real `f32` rounding** (`Dtype::round_for_mode`): compat-reference
computes every dtype at full `f64` precision internally and never
rounds an `f32`-declared Tensor's data to actual `f32` precision except
at `.rstensor`/`to_array` I/O boundaries (matching the Python
reference's own "f32 metadataでも内部はbinary64相当で計算する" contract,
section 10). `round_for_mode` is a strict superset of the existing
`Dtype::cast` (bool/i32/i64 behavior is identical in both modes; only
`f32` differs): in `NativeFast`, an `f32`-dtype value is additionally
round-tripped through a real `f32` (`value as f32 as f64`) at every
`TensorStore::insert()` -- i.e. at every intermediate Tensor a
computation produces, not just its final output. This gives the exact
numerically-correct `f32` result at every step (the correctly-rounded
`f32` value for that computation, identical to what genuine narrow
`f32` storage would produce) without this crate needing a second,
narrower `TensorData` representation -- the honest tradeoff being that
this captures real `f32` *accuracy* behavior but not the memory-
bandwidth benefit of packed `f32` storage; the speedup this phase
delivers comes entirely from parallelism, not from narrower storage.

**Parallel CPU** (`ops.rs`'s `broadcast_binary_parallel`/
`unary_parallel`/`reduce_parallel`/`matmul_parallel`, dispatched only
from `NativeFast` branches added to `tensor_dispatch.rs`'s `binary`/
`divide`/`unary`/`reduce`/`linalg_matmul`): `rayon`-parallelized, each
proven deterministic *by construction*, not by luck -- documented per
function in `ops.rs`:
- Elementwise ops (`broadcast_binary`/`unary`) are trivially safe: every
  output element depends only on its own input element(s), and
  `par_iter().map(..).collect()` always preserves source order.
- `matmul` parallelizes across output *rows*; each row's `k`-length
  inner dot product is still a strictly sequential fold in the exact
  same fixed order the sequential version uses.
- `reduce` parallelizes *across* independent output groups; each
  group's own reduction is still a sequential fold over that group's
  elements in the same fixed (source flat-index) order the sequential
  version builds it in. A reduction to a *single* output group (e.g.
  `axis: None` reducing a whole Tensor to one scalar) gets no
  parallelism from this pass -- there's nothing to split across groups
  when there's only one, and splitting *within* one group's sum would
  reorder floating-point summation (exactly what `CompatReference`
  forbids) -- a documented limitation, not attempted here.

**Verified**: `ops.rs`'s own `#[cfg(test)]` module (5 new tests) proves
every `_parallel` function is bit-exact against its sequential twin on
non-trivial inputs, and that `round_for_mode` only ever rounds `f32` in
`NativeFast`. `computation_ir_tests/test_computation_ir_native_fast_mode.py`
(7 tests, via the built binary + the env var) covers: the default
(unset env var) behaves identically to explicit `compat-reference`, and
an unrecognized mode value also falls back to it; `f32` rounding is
real (a value exactly representable in `f64` but not `f32` differs
between modes); `f64` matmul/reduce are bit-exact between modes
(parallelism alone, no precision difference); native-fast is
deterministic across three separate process invocations of the same
workload; and an `f32` matmul is numerically close (not bit-exact, by
design) between modes.

**Measured, not fabricated**: `scripts/benchmark_native_fast.py` shells
out to the built binary in both modes for a `matmul + add + sum`
workload and reports real wall-clock numbers. On this session's
environment (4 CPU cores, no BLAS, no GPU): a 700×700 matmul workload
measured **1.42x** (compat-reference 1.03s vs. native-fast 0.72s, best
of 5). This is real but far below the plan's "10倍以上" gate -- that
gate bundles BLAS and GPU, neither of which is in this phase's scope,
and 4 cores caps plain-CPU parallelism's ceiling well under 10x anyway.
Reported honestly rather than claiming the plan's target number.

**Not implemented** (documented gaps): BLAS (no system library
available in this environment; a pure-Rust alternative like
`matrixmultiply` was not attempted either, to keep this pass's surface
area proportionate to what was actually asked for), GPU (no hardware),
a cost model (auto-selecting a mode/backend per workload is speculative
without real benchmarking data from an actual target workload --
`NumericMode` is explicit opt-in only, never auto-selected), and a
narrower packed `f32`/`f64` `TensorData` storage representation (the
"real memory bandwidth savings" half of true `f32` -- this pass gets
`f32`'s *numerical* behavior via rounding, not its *storage* footprint).

## Modernization Plan — Phase 10 Approximate Tensor Logic (SVD Foundation Only)

Phase 10's full scope ("Tucker optimizer/rank選択/denoise", gate
"end-to-end 2倍以上またはメモリ改善、accuracy低下0.5pt以内") was checked
against this repository before starting: no SVD, eigendecomposition, or
Tucker decomposition existed anywhere, on either the Python or Rust
side. Unlike `optimizer.*`/`relation.*` (composable from existing
elementwise/comparison primitives), a correct Tucker decomposition needs
a real linear-algebra algorithm as its foundation, with no existing
implementation to port from or differentially test against, and the
"end-to-end"/"accuracy低下0.5pt以内" gate is (like every prior phase's
Model D-tied gate) unmeasurable here regardless. Per an explicit scope
decision, this phase is narrowed to exactly that missing foundation: a
minimal SVD (rank-2 matrices only -- "rank" here means *tensor* rank,
i.e. a matrix, not the linear-algebra rank of the matrix's row/column
space). Tucker decomposition itself (mode-n unfolding/refolding, N-way
core tensor computation, rank-selection/tolerance policy, the
`@approximate(method="tucker", ...)` language surface) is NOT
implemented -- real, separate, follow-up work once this foundation
exists to build on.

**Algorithm**: one-sided Jacobi SVD (Hestenes' method) --
`frontend/tensor/linalg.py`'s `svd()` and
`ReasonComputationRuntime/crates/tensor-core/src/linalg.rs`'s `svd()`
implement the identical algorithm independently on both sides: repeatedly
rotate pairs of columns of a working copy of the input matrix toward
orthogonality (accumulating the rotations into `V`) until the Gram
matrix's off-diagonal energy falls below tolerance or a sweep limit is
hit; singular values are the converged working columns' norms, `U` is
those columns normalized. Chosen over eigendecomposing `A^T @ A`
because it never squares the matrix's condition number, while still
being simple enough to implement and verify correctly with no existing
oracle.

**Deliberately internal, not language-surface-facing yet**: a full SVD
naturally produces three differently-shaped outputs (`U`, singular
values, `V`), which would hit the exact same "no synthetic struct
return type" problem `frontend/tensor/optimizers.py`'s module docstring
documents for `optimizer.*` -- not solved here (it's a real, separate
design decision, same as `join`/`project` in Phase 8). `svd` is
therefore not wired into `tensor_dispatch.rs`/the IR/the language
surface at all; it exists purely as a building block for whenever
Tucker decomposition itself gets built.

**Verification, without the usual differential-test pattern**: since
`svd` isn't reachable through the IR/CLI, the normal "lower once, run
through both Python and Rust, compare `calculation_results`" pattern
doesn't apply. Instead, both sides are verified independently against
the *same* closed-form values and mathematical invariants -- a
divergence between the two implementations would surface as one side's
test failing to match the shared expected numbers, even without a
process-level harness:
- Closed-form singular values for known matrices (a rank-deficient
  matrix `[[3,0],[4,0]]` → singular values `5, 0`; a diagonal matrix →
  its sorted diagonal; a rank-1 outer product `a ⊗ b` → a single
  singular value `|a|·|b|`; the identity matrix → all-`1` singular
  values and identity factors).
- Reconstruction: `U @ diag(S) @ V^T` matches the original matrix to
  ~1e-8 for random square/tall/wide matrices up to 6×6.
- Orthogonality: `U^T @ U` and `V^T @ V` are the identity to ~1e-8.
- Singular values are always sorted descending and never negative.

4 new Rust unit tests (`linalg.rs`) and 10 new Python tests
(`tensor_standard_functions_tests/test_linalg_svd.py`), covering the
above on both sides with matching input matrices.

**Not implemented** (documented gaps): Tucker decomposition itself
(mode-n unfolding/refolding, core tensor computation, rank selection,
the `@approximate` syntax), higher-order (rank > 2) tensor
decompositions, a denoising story, and the end-to-end
speedup/memory/accuracy gate (no Model D/Transformer fixture exists
here to measure it against, same as every prior phase's benchmark
gate).

## Development Environment

`reason ci` requires the packages in `requirements-dev.txt` (pydantic,
pytest, fastapi, ...) installed into the *same* Python interpreter used to
invoke `reason`. A system Python, or an unrelated sandboxed venv that does
not have these packages installed, will fail either at import time
(`ModuleNotFoundError`, e.g. missing `pydantic`) or during the Tests phase
(`CI-008`, missing `pytest`).

A `Dockerfile` is provided at the repository root that reproduces the same
environment used by `.github/workflows/ci.yml` and `test.yml` (Rust
toolchain, system libraries, and `requirements-dev.txt` installed into a
dedicated venv). Coding agents running in a container should build and use
it instead of an ad-hoc host interpreter:

```sh
docker build -t reasonscript-dev .
docker run --rm -v "$PWD:/workspace" reasonscript-dev ./reason ci --json
```

If running outside the container, install dev dependencies into whichever
interpreter you invoke `reason` with:

```sh
python3 -m pip install -r requirements-dev.txt
```

## CI Stabilization

This repository follows `reasonscript-ci/1.0` for CI execution. The canonical workflow runs:

1. Checkout Repository
2. Environment Setup
3. Workspace Validation
4. Diagnostics Validation
5. Artifact Validation
6. Golden Tests
7. Agent Protocol Validation
8. Compatibility Verification
9. Unit / Integration Tests
10. Completion Report

Run the full pipeline locally with:

```sh
reason ci --json
```

The pipeline generates `ci_report.json` and `ci_summary.json`. Every validation failure terminates the pipeline and reports the failing phase.

### CI Validation Rules

- `CI-001`: Missing workflow
- `CI-002`: Required command failed
- `CI-003`: Workspace validation failed
- `CI-004`: Diagnostics validation failed
- `CI-005`: Artifact validation failed
- `CI-006`: Golden test failed
- `CI-007`: Agent protocol violation
- `CI-008`: Test failure
- `CI-009`: Compatibility failure
- `CI-010`: Report generation failure

## Canonical CI Entry Point

This repository follows `reasonscript-ci-entry/1.0`. Beginning with ReasonScript Development Platform v0.5, `reason ci` is the single official validation command for local development, Coding Agents, and CI. Individual commands remain implementation-level interfaces and do not replace it.

### Coding Agent Policy

Coding Agents shall execute `reason ci` before reporting task completion. Execution of individual commands is permitted for diagnosis, debugging, or incremental development but does not replace the canonical validation workflow.

### CI Policy

GitHub Actions and equivalent CI systems shall invoke `reason ci` as the primary validation command. Platform-specific scripts shall not duplicate the validation pipeline unless required for infrastructure reasons.

### Entry Point Validation Rules

- `CE-001`: Missing CI pipeline
- `CE-002`: Invalid execution order
- `CE-003`: Required validation omitted
- `CE-004`: Report generation failure
- `CE-005`: Pipeline termination failure

## Protocol Validation Rules

- `AP-001`: Missing specification
- `AP-002`: Missing validation
- `AP-003`: Missing artifacts
- `AP-004`: Golden failure
- `AP-005`: Invalid task state
- `AP-006`: Incomplete completion report
- `AP-007`: Protocol violation
- `AP-008`: Manual artifact modification
- `AP-009`: Required command skipped
- `AP-010`: Unrecorded compatibility change
