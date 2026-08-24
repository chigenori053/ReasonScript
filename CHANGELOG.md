# Changelog

## Unreleased

### Fixed

- Completed first-class ReasonUnit Object bindings in the language and Python
  computation runtimes. `ReasonObject` and related opaque RUO types now resolve
  in function signatures, `reason_object` identifiers infer `ReasonObject`,
  `ruo.*` calls provide result types and statically reject known argument-kind
  mismatches, and both the AST evaluator and Python Computation IR interpreter
  execute capability-confined Object bindings through a shared dispatcher.
  Added `call_ruo` and Object binding records to `reason-computation-ir/0.1`;
  the Rust VM now verifies native Objects and executes identity, snapshot,
  resolution, status, and diagnostics, with the remaining operations routed to
  the Python fallback. RUO-W1 world-level cutover remains explicitly deferred.

- Hardened the `optimizer.*` implementation after a completeness audit:
  `optimizer_dispatch.rs` now checks argument count upfront (a hand-built
  IR document with too few arguments previously panicked via an
  unchecked slice index instead of returning `OPT-002` -- unreachable
  from real `.rsn` source, but a real robustness gap for hand-built IR);
  `TensorRuntime.call_optimizer` now accepts and attaches
  `_source_location` to raised errors, matching `call()`'s diagnostics
  (both the IR interpreter and the AST evaluator now thread it through);
  named-argument syntax on an `optimizer.*` call is now rejected with
  `OPT-002` at parse time instead of falling through to a misleading
  `TSF-016` Tensor diagnostic. 4 new regression tests.

### Added

- Completed Rust runtime consolidation Phase 8: renamed the primary workspace
  to `ReasonRuntime/`, moved the RUO and Vision libraries/binaries into
  `crates/reason-object-core` and `crates/vision-core`, switched build/install/
  validation discovery to the unified workspace target, and deleted the
  superseded `ReasonComputationRuntime`, `NativeReasonUnitRuntime`, and
  `VisionRuntime` directory layouts and duplicate Cargo lockfiles.

- Completed Rust runtime consolidation Phase 7: removed Python evaluator
  fallback from standalone and project execution, switched project validation
  and `reason tensor import|inspect|verify` to the Rust host, and separated the
  compiler's Tensor contract registry from the Python Tensor evaluator. Native
  host/lowering/capability/bridge/runtime failures now remain structured Rust
  diagnostics. Python evaluators are retained only as differential-test and
  benchmark references pending their final deletion gates.

- Completed Rust runtime consolidation Phase 6: added an in-process Rust
  reasoning core for `runtime.search`, `runtime.simulate`, `runtime.predict`,
  and `runtime.plan`; lowered those calls through Computation IR; propagated
  RuntimeReal/HybridRuntime backend selection; and returned native reasoning
  result, trace, and ExecutionPlan data. Differential tests freeze the existing
  Optional result and diagnostic ABI against both Python reference evaluators.

- Completed Rust runtime consolidation Phase 5: all 16 `ruo.*` functions and
  both `vision.*` functions now execute as libraries inside the Rust runtime
  host. Added canonical RUO-F1 save/publication, transaction and query parity,
  Vision capability/path enforcement, native Vision trace, and differential
  Python/Rust tests for results, diagnostics, saved Objects, and Tensor
  resources. The Python RUO/Vision runtimes remain reference/fallback code
  pending the Phase 7 retirement gates.

- Added Phase 10's minimal SVD foundation (narrowed from the full
  "Tucker optimizer/rank選択/denoise" scope after confirming no SVD,
  eigendecomposition, or Tucker decomposition existed anywhere in this
  repository to build Tucker on top of): a one-sided Jacobi SVD
  (Hestenes' method) implemented identically and independently in
  `frontend/tensor/linalg.py` and
  `ReasonComputationRuntime/crates/tensor-core/src/linalg.rs`. Not
  wired into the `tensor.*` language surface/IR yet -- `U`/singular
  values/`V` are three differently-shaped outputs, hitting the same
  "no synthetic struct return type" gap `optimizer.*`'s `join`/`project`
  already document, a real separate design decision. Verified against
  closed-form singular values, reconstruction accuracy, and `U`/`V`
  orthogonality on both sides independently (no IR/CLI path exists yet
  for the usual subprocess differential test, so both implementations
  are checked against the same shared expected values instead). 4 new
  Rust unit tests, 10 new Python tests
  (`tensor_standard_functions_tests/test_linalg_svd.py`). Tucker
  decomposition itself (mode-n unfolding, core tensor computation, rank
  selection, `@approximate` syntax) remains real follow-up work; see
  AGENTS.md.
- Added Phase 9's `NumericMode::NativeFast` (narrowed after checking
  this environment has no GPU and no system BLAS library, and after a
  scope decision to skip a cost model): a second numeric mode alongside
  the existing, default, completely unchanged `CompatReference`,
  selected via `REASONSCRIPT_NUMERIC_MODE=native-fast` on the Rust CLI.
  Real `f32` rounding (`Dtype::round_for_mode`, a strict superset of the
  existing `cast`) at every intermediate Tensor a native-fast
  computation produces, and `rayon`-parallelized elementwise/unary/
  reduce/matmul op paths in `reasonscript-tensor-core`'s `ops.rs`, each
  proven deterministic by construction (documented per function: fixed
  per-row/per-group sequential accumulation order, never a
  floating-point summation reorder) rather than by luck. 5 new Rust
  unit tests proving bit-exact parity between each parallel function
  and its sequential twin, plus 7 new Python tests
  (`computation_ir_tests/test_computation_ir_native_fast_mode.py`)
  covering default-mode equivalence, real f32 rounding, f64 bit-exact
  parity between modes, and determinism across repeated process
  invocations. `scripts/benchmark_native_fast.py` measures real
  wall-clock speedup (1.42x on this session's 4-core, no-BLAS, no-GPU
  environment for a 700×700 matmul workload) rather than reporting the
  plan's un-validatable "10倍以上" target, which bundles BLAS and GPU
  that are both out of scope here. See AGENTS.md for the full design
  writeup and what's still Pending (BLAS, GPU, a cost model, packed
  `f32`/`f64` storage).
- Added the `relation.*` namespace (Phase 8, "Tensor Logic hybrid",
  narrowed to its relational-algebra core after a scope decision):
  `filter_eq`/`filter_ne`/`filter_gt`/`filter_gte`/`filter_lt`/`filter_lte`,
  `count`, `distinct_by`, and `sort_by` over `Array<Struct>`
  (ReasonScript's existing "array of same-shaped structs" IS a
  relation's tuple set). All type-preserving (input/output share the
  same `Array<Struct>` type), so no synthetic struct return type is
  needed -- `join`/`project` are NOT implemented, since both change a
  row's field shape and hit a real static-typing gap (no way to
  synthesize a `StructDeclarationNode` for a derived field set); this
  needs its own design decision, not made here. Every filter/sort field
  argument is a required string literal (`REL-003` otherwise):
  ReasonScript has no closures, so an arbitrary predicate can't be
  passed. New `call_relation` IR node
  (`frontend/computation_ir/schema.py`), a plain module-level
  `call_relation` dispatcher in `frontend/integrated_computation_runtime.py`
  (no persistent state -- every function is a pure `Array<Struct>` read)
  used by both the AST evaluator and the IR interpreter, and
  `ReasonComputationRuntime/crates/computation-ir/src/relation_dispatch.rs`
  reusing `vm::eval_comparison` directly. New `REL-001`..`REL-007`
  diagnostic family, kept outside the Tensor Standard Functions
  contract. The Phase 7 IR optimizer treats `call_relation` like
  `call_tensor`/`call_optimizer` (side-effect-free, never
  CSE-deduplicated). 19 new differential Python/Rust tests
  (`computation_ir_tests/test_computation_ir_relation_functions.py`),
  plus 3 more covering its interaction with the Phase 7 IR optimizer.
  Found and fixed two real parity/correctness bugs during development:
  Python's `distinct_by` originally used a hash set (raises on an
  unhashable field value, unlike Rust's linear equality scan) --
  switched to a linear scan on both sides; Rust's `sort_by` comparator
  originally derived `Ordering` naively from a single `<` check
  (reports `Greater` for two *equal* fields in both directions, an
  inconsistent comparator) -- fixed to derive a proper 3-way ordering
  from two `<` comparisons, matching Python's `sorted()`. See AGENTS.md
  for the full design writeup, including why the dense/sparse Tensor
  partitioning half of Phase 8 and anything tied to the plan's
  Transformer-specific "Relation Matrix" framing remain out of scope
  (no fixture in this repository).

- Added the `optimizer.*` namespace (SGD, Momentum, Adam, AdamW),
  previously deferred as "Pending -- explicitly deferred as a separate
  scope decision". New language surface (`frontend/tensor/optimizers.py`),
  a new `call_optimizer` IR node alongside `call_tensor`/`call_vision`,
  and a shared numeric implementation in both engines
  (`TensorRuntime.call_optimizer` composed from the same elementwise
  primitives `tensor.*` uses but never autograd-taped, and
  `ReasonComputationRuntime/crates/computation-ir/src/optimizer_dispatch.rs`
  composed the same way from `reasonscript_tensor_core::ops::broadcast_binary`).
  Every function returns a single Tensor (`optimizer.sgd`,
  `optimizer.momentum_velocity`/`optimizer.momentum`,
  `optimizer.adam_moment1`/`optimizer.adam_moment2`/`optimizer.adam`,
  `optimizer.adamw`) rather than a struct, working around a real gap in
  the static type checker (no field access on a synthetic struct return
  type). Deliberately kept outside the Tensor Standard Functions
  contract (`tensor_function_manifest.json`/`reason tensor-manifest
  --check` untouched) with its own `OPT-001`..`OPT-005` diagnostics. 13
  new differential Python/Rust tests
  (`computation_ir_tests/test_computation_ir_optimizer_functions.py`),
  including a 30-iteration Adam training loop that actually converges.
  Both the AST evaluator and the IR interpreter dispatch `optimizer.*`
  calls; the Phase 7 IR optimizer treats `call_optimizer` like
  `call_tensor` (side-effect-free, never CSE-deduplicated). See
  AGENTS.md for the full design writeup and documented gaps (no
  stateful `optimizer.step(handle, ...)` object API, no LR schedulers,
  no gradient clipping).
- Added Phase 7 "IR最適化" (`frontend/computation_ir/optimizer.py`,
  `optimize_program`): constant folding (arithmetic/comparison/unary/
  logical short-circuit/cast, leaving divide-or-modulo-by-zero unfolded
  so RT-ARITH-001 still raises correctly), dead branch elimination,
  unreachable block removal, dead local elimination (never eliminating
  `tensor.load`/`tensor.save`), and local (single-block) common
  subexpression elimination (never deduplicating Tensor/vision/function/
  array-append calls). Runs once on the shared
  `reason-computation-ir/0.1` JSON, benefiting both the Python
  interpreter and the Rust `reason-computation-runtime`. New CLI flag
  `reason computation-ir --optimize`. 18 new differential tests
  (`computation_ir_tests/test_computation_ir_optimizer.py`, comparing
  unoptimized/optimized results across both Python and Rust), including
  a regression test for a self-referential-assign CSE cache-poisoning
  bug (`i = i + 1`) found and fixed during development. Cross-block CSE,
  loop-invariant code motion, a Relation Matrix cache, a compile-time
  gradient-pruning pass, Tensor buffer reuse, and kernel fusion are
  explicitly out of scope (see AGENTS.md for why). Optimizers (SGD/
  Momentum/Adam/AdamW) remain Pending, unaffected by this phase.
- Added Phase 6 "Rust default execution" to `scripts/reason_cli.py`
  (`_run_result`/`_try_rust_execution`): `reason run`/`reason check` now
  try the Rust computation runtime first for calculation/Tensor
  programs, transparently falling back to the Python AST evaluator for
  an unsupported construct, `tensor.load`/`save` without filesystem
  capabilities granted, a trace request (`--trace`/`--json`, since Rust
  doesn't produce trace/metadata parity yet), or any genuine runtime
  error (re-derived via Python's own diagnostic path rather than
  reshaping a Rust error here). `result["execution_mode"]` is now
  `"integrated-rust"` when Rust ran the program. Added opt-in shadow
  mode (`REASONSCRIPT_SHADOW_MODE=1`): re-runs a Rust-executed program
  through Python and warns on stderr (without failing) if they disagree.
  `runtime-cli`'s `serde_json` now uses `preserve_order` so
  `calculation_results` comes back in execution order rather than
  alphabetized. 8 new tests
  (`runtime_completeness_tests/test_phase6_rust_default_dispatch.py`).
  Optimizers (SGD/Momentum/Adam/AdamW) remain Pending, per an explicit
  decision to treat that as separate, not-yet-scoped work (see AGENTS.md).
- Added Phase 5 "Rust Autograd" to `reasonscript-tensor-core`
  (`autograd.rs`: tape + VJPs for every differentiable forward op the
  crate implements) and wired `parameter`/`detach`/`requires_grad`/`grad`
  into `tensor_dispatch.rs`, matching Python's `_GradNode`/`_vjp`/
  `TensorRuntime.grad` exactly (including first-occurrence tie-breaking
  for min/max gradients). Verified via a standalone Rust finite-difference
  unit test (no Python needed), 18 new differential parity tests
  (`computation_ir_tests/test_computation_ir_autograd_parity.py`), and a
  hand-rolled 20-step gradient-descent loop matching `0.8**20` to full
  f64 precision in both languages. Found and fixed a real bug along the
  way: Python's broadcast ops (`add`/`multiply`/...) silently auto-box a
  bare scalar/array literal operand into an untracked Tensor
  (`_operand()`); the initial Rust port required an explicit Tensor
  handle for both operands and rejected `tensor.multiply(x, 0.1)` with
  `RT-CALL-005` until `operand_id()` was added to mirror that. Optimizers
  (SGD/Momentum/Adam/AdamW) are explicitly NOT implemented: there is no
  `optimizer.*` namespace anywhere in ReasonScript's language surface or
  Python runtime to port from or diff against (see AGENTS.md).
- Added `reasonscript-tensor-core` to `ReasonComputationRuntime/`,
  implementing Phase 4 ("Rust Tensor forward"): Tensor storage/handle,
  dtype system (compat-reference: f64 internally regardless of declared
  dtype), dense CPU reference ops, a SHA-256-counter RNG matching Python
  byte-for-byte, and `.rstensor` encode/decode with verified
  bidirectional cross-language interop (Rust writes/Python reads and
  vice versa). Wired into `computation-ir`'s VM via
  `tensor_dispatch.rs`, which now executes ~50 of the 65 Tensor Standard
  Functions for real (creation, inspection, shape ops, broadcast
  binary/comparison/unary elementwise, reductions, dot/matmul/norm,
  cast, to_array/scalar, the 4 RNG functions, load/save) rather than
  always returning `RT-UNSUPPORTED-001`. `slice`/`narrow`/`gather`/
  `concat`/`stack`, the neural-net inference ops
  (`relu`/`softmax`/`linear`/`conv2d`/`max_pool2d`/`avg_pool2d`), and
  autograd (`parameter`/`detach`/`requires_grad`/`grad`, Phase 5) remain
  `RT-UNSUPPORTED-001`. Found and fixed a real cross-language semantic
  gap along the way: Python `float / 0.0` raises at computation time
  (normalized to `TensorError("TSF-012", ...)`) while Rust's `f64`
  division silently produces `inf`; the Rust divide op now pre-checks
  for a zero divisor to match. 16 new differential tests
  (`computation_ir_tests/test_computation_ir_tensor_parity.py`), all
  passing, including exact RNG value equality and both `.rstensor`
  interop directions.
- Added `ReasonComputationRuntime/`, a new independent Cargo workspace
  implementing the Phase 3 "Rust VM skeleton": `computation-ir` (a
  `reason-computation-ir/0.1` decoder plus a Tensor-less basic-block VM
  matching `frontend/computation_ir/interpreter.py`'s semantics and RT-*
  error codes instruction-for-instruction) and `runtime-cli` (the
  `reason-computation-runtime` binary). `call_tensor`/`call_vision`
  return `RT-UNSUPPORTED-001` rather than executing (Phase 4+ scope).
  `frontend/computation_ir/rust_bridge.py` +
  `computation_ir_tests/test_computation_ir_rust_parity.py` implement the
  Phase 3 gate ("Tensorなしcalculationのpython/Rust一致"), skipping (not
  failing) if the binary isn't built.
  `scripts/test_platform.py`'s `RUST_CRATES`/`RUST_TEST_CRATES` now
  include it, so `python3 scripts/test_platform.py test` builds and
  `cargo test`s it before the Python parity tests run.
- Added `frontend.computation_ir`: a Phase 2 `reason-computation-ir/0.1`
  implementation — AST-to-basic-block lowering (`lowering.py`), a
  temporary Python interpreter for that IR (`interpreter.py`), structural
  schema validation (`validation.py`), and a differential test harness
  proving the IR interpreter agrees with the existing AST evaluator
  (`differential.py`, `computation_ir_tests/`). Exposed via
  `reason computation-ir [--json] [--validate] <file.rsn>`. Rust work is
  explicitly out of scope for this phase; see AGENTS.md for the exact
  language-construct coverage and known scope limits.
- Added `float(x)` / `int(x)` explicit numeric conversion builtins
  (ReasonScript modernization plan L-004). `int(x)` truncates toward
  zero. Validated in `frontend/language_surface/validation.py`
  (`CAST-001`/`CAST-002`), evaluated in
  `frontend/integrated_computation_runtime.py` (`RT-CALL-005`) and
  `frontend/language_surface/integration.py`'s compile-time folding.
- Added `TensorRuntime.no_grad()` (`frontend/tensor/runtime.py`), a
  context manager that suppresses autograd tape recording for its
  duration, implementing the plan's "evaluationをno-gradにする" Phase 1
  item.

- Added `reason tensor-manifest`, which emits a frozen
  `reasonscript-tensor-function-manifest/1.0` JSON manifest of every
  `tensor.*` function's argument/return/diagnostic contract, and a
  `--check` mode that fails when the live contract set drifts from the
  committed baseline (`docs/reports/tensor_function_manifest.json`). A
  regression test (`tensor_standard_functions_tests/test_tensor_function_manifest.py`)
  enforces this baseline in CI. This is the "契約manifest化 / 契約凍結"
  Phase 0 baseline task from the ReasonScript modernization plan.
- Added `scripts/benchmark_tensor.py` (`make benchmark-tensor`), a
  micro/operator-tier benchmark harness measuring per-call latency of the
  current Python Tensor runtime (cast/dispatch, elementwise, reduction,
  matmul, softmax, gather), producing a `reasonscript-tensor-benchmark/1.0`
  JSON report. This establishes the Phase 0 "before" baseline the plan's
  later Rust runtime and IR-optimizer phases are meant to be measured
  against.

### Fixed

- Fixed `/` and `%` leaking a raw Python `ZeroDivisionError` out of
  `frontend/integrated_computation_runtime.py`'s expression evaluator
  instead of the `IntegratedRuntimeError` diagnostic every other failure
  path there uses. Division/modulo by zero now raises
  `IntegratedRuntimeError("RT-ARITH-001", ...)`. Found while implementing
  the L-006 DIVIDE type fix below; Tensor division-by-zero was already
  handled correctly (wrapped as `TensorError("TSF-012", ...)` at the
  `TensorRuntime.call()` boundary), so this inconsistency was isolated to
  the scalar language evaluator.
- Fixed the static type checker returning `Int` for `Int / Int` when `/`
  actually evaluates to a Python float at runtime (a real type/value
  mismatch). `/` is now always typed `Float`, matching its true-division
  runtime semantics (ReasonScript modernization plan L-006, partial: `//`
  is not introduced, since it is the existing line-comment token).

## v0.5.4.5 — 2026-08-07

### Added

- Added Tensor Training Foundation v0.2 with NCHW Conv2d, MaxPool2d,
  AvgPool2d, reverse-mode automatic differentiation, slice/gather, stateless
  seeded random Tensor creation, and bounded autograd lifecycle management.
- Added the checksum-verified `.rstensor` file profile, capability-checked
  `tensor.load` / `tensor.save`, and `reason tensor import|inspect|verify`
  commands for JSON, CSV, and optional NumPy input.

### Fixed

- Released Tensor backend values after they become unreachable from integrated
  runtime environments, preventing iterative tensor programs from exhausting
  the 1,000-live-value policy.
- Kept loop trace snapshots bounded by serializing Tensor metadata instead of
  implicitly materializing every element through `tensor.to_array`.
- Accepted decimal scientific notation in ReasonScript numeric literals.
- Propagated parsed Tensor call locations into runtime diagnostics and tensor
  trace source references.

### Changed

- Cleaned up repository documentation for the open-source release: removed
  internal validation reports, phase completion reports, and audit artifacts;
  added a documentation index at `docs/README.md`.

## v0.5.4.4 — 2026-08-02

### Added

- Added a file-tree overlay to `reason view` (the `e` key): pass a
  directory, or nothing at all, to browse a project's `.rsn` files instead
  of naming one up front. The tree auto-picks a starting file, highlights
  whichever file is currently open, and lets `j`/`k`/`h`/`l`/`Enter`/`Esc`
  navigate, expand/collapse, and select. `--root <dir>` scopes the tree
  independently of which file was opened. `--json`/`--plain` still require
  a specific file (`CV-007`); a directory with no `.rsn` files anywhere
  under it is `CV-008`. See `docs/development/code_viewer_design.md` §17.

## v0.5.4.3 — 2026-08-02

### Added

- Added `reason view`, a terminal CodeViewer that browses a `.rsn` source
  file alongside its compiled Surface AST, Semantic AST, Reason IR, and
  ExecutionPlan, correlating the declaration under the cursor with the
  stage nodes derived from it. Supports `--json` and `--plain` output for
  CI/agent use, and an interactive curses UI (search, stage-node JSON
  pointer copy, an all-stages diagnostics summary) when attached to a real
  terminal. Non-interactive environments automatically get `--plain`
  output. On Windows, the interactive UI requires the new optional
  `windows-curses` dependency (`pip install 'reasonscript[viewer]'`);
  without it, `reason view` still works via the `--plain` fallback.
  See `docs/development/code_viewer_design.md` and
  `docs/reference/ReasonScript_v0_5_CLI_Reference.md`.

## v0.5.4.2 — 2026-07-28

### Added

- Added the Safe-Rust Semantic Visualization Runtime v0.1 with deterministic
  2D Semantic Scene projection, validation, transactions, SVG output, and
  canonical evidence-bearing artifacts.
- Added `reason visualization` and packaged `reason-visualization` native
  runtime support, including staged and installed distribution validation.

## v0.5.2.4 — 2026-07-25

### Fixed

- Unified standalone and canonical CI Golden corpus results, retained
  actionable underlying diagnostics, and added `GT-011` for a missing corpus.
- Added compact single-line `struct` declarations with nested composite type
  support and `PARSE-001` diagnostics for malformed declarations.
- Added successful global `reason --help`, `reason -h`, and `reason help`
  discovery.

## v0.5.2.3 — 2026-07-25

### Fixed

- Corrected nested function-call lowering to evaluate inner calls before
  branching outer calls, merge alternative inner return states without
  duplicate transition IDs, and pass literal inner results into outer branch
  evaluation.
- Added multiline typed function parameter-list parsing.

## v0.5.2.2 — 2026-07-24

### Fixed

- Corrected RUO native runtime discovery so installed `reason object` and
  `reasonunit-runtime` commands resolve binaries from the active distribution
  rather than the caller's project directory.
- Corrected Python/Rust RUO-F1 interoperability by hashing the canonical raw
  record body in the native reader instead of a re-serialized JSON value.
- Added exponent-number, VisionRuntime-to-RUO, arbitrary-working-directory,
  and record-tamper regression coverage.

### Validation

- Focused RUO-F1/N1/N2/Vision regression: 54 PASS.
- Native Rust tests, Clippy, and rustfmt: PASS.
- `reason ci --json`: PASS, 1092 tests.

## v0.5.2.1 — 2026-07-23

### Fixed

- Restored every provenance-declared executable after ZIP extraction and added
  pre-activation native runtime probes, preventing `reason-vision` and
  `reasonunit-runtime-native` from reaching validation with mode `0644`.
- Added a bounded packaged-CLI permission bootstrap so the v0.5.1 updater can
  activate v0.5.2.1 without requiring a prior updater hotfix.
- Preserved per-command post-install diagnostics in update, validation, and
  automatic rollback reports.

### Added

- Implemented Integrated Runtime Completeness v0.2:
  - Scalar-only calculations now use the integrated numerical runtime without
    requiring Tensor, Vision, or loop trigger syntax.
  - Added array index access/assignment, user functions, struct values/member
    access/field assignment, deterministic `array.append`, and atomic
    `reason run --result-output PATH`.
  - Added installed/development resolution, packaging, and staged smoke
    validation for `reasonunit-runtime-native`.
  - Clarified that `reason object` owns canonical Object operations rather than
    numerical physics evaluation.

- Implemented ReasonScript Phase RUO-M1 Legacy ReasonUnit Migration v1.0:
  - Added deterministic read-only discovery and classification, SHA-256 source
    freeze, semantic authority analysis, versioned plans, stable-ID preservation
    and semantic-locator ID generation, bidirectional traceability, and bounded
    offline input handling.
  - Added staging-only conversion to canonical RUO-U1/RUO-F1 Objects and RUO-T1
    resources, lossless `legacy` extension retention, semantic reconstruction
    comparison, and direct RUO-N1 native and RUO-N2 binding validation.
  - Added explicit project-atomic publication, generated consumer bindings,
    source/plan-bound evidence, idempotent republishing, and rollback that
    preserves both prior and migrated evidence.
  - Added the consolidated `reason object migrate` workflow, 21 fixture
    classes, all 24 diagnostics, a project-owned schema, 57 canonical
    artifacts, and six inventoried migration fixture files.

### RUO-M1 Validation

- RUO-M1 matrix: 63/63 PASS; dedicated migration tests: 20 PASS.
- Focused RUO regression: 163 PASS.
- Native Rust checks, Clippy, rustfmt, and Agent Protocol: PASS.
- `reason ci --json`: PASS, 1071 tests.

- Implemented ReasonScript Phase RUO-N2 ReasonUnit Object Language and CLI
  Integration v1.0:
  - Added nested `reason_object` bindings for `model` and compatibility
    `module`, deterministic clause/source spans, static path and identity
    validation, stable `ReasonObjectBindingIR`, typed `ReasonObjectOperationIR`,
    and explicit capability/native-load/transaction/save execution-plan stages.
  - Added all 12 RUO opaque language types, 10 presence/failure states, and 16
    versioned `ruo.*` standard functions mapped to RUO-N1 native operations.
  - Added the consolidated `reason object` CLI, deterministic formatter,
    capability-gated native loading and atomic persistence, seven offline
    examples, 28 invalid cases, a project-owned schema, and all 56 canonical
    artifacts.
  - Recorded the additive RUO-N1 implementation-status normalization without
    changing any RUO-N1 historical canonical artifact.

### RUO-N2 Validation

- RUO-N2 matrix: 67/67 PASS; dedicated integration tests: 17 PASS.
- Focused RUO and language compatibility regression: 159 PASS.
- Native Rust tests: 5 passed; Clippy and rustfmt: PASS.
- `reason ci --json`: PASS, 1051 tests.
- Agent Protocol: PASS.

- Implemented ReasonScript Phase RUO-N1 Native ReasonUnit Object Runtime Type v1.0:
  - Added the safe-Rust `NativeReasonUnitRuntime` core with namespaced stable IDs,
    generation-checked handles, deterministic native registries, immutable
    concurrent-read snapshots, atomic optimistic transactions, native queries,
    resource lifecycle contracts, Tensor views, and explicit Runtime/Cluster
    projections.
  - Added native RUO-F1 loading and byte-preserving snapshot writing, the thin
    `reason reasonunit-runtime` CLI boundary, 21 fixture classes, 26 hostile and
    invalid cases, a project-owned artifact schema, and all 54 RUO-N1 canonical
    artifacts.
  - Validated RUO-N1-T001 through T074, three-run byte equality, zero unsafe
    blocks, reference/native parity, prerequisite preservation, and transition
    `PROCEED_TO_RUO-N2`.

### Validation

- Native Rust tests: 5 passed; Clippy and rustfmt: PASS.
- Earlier RUO focused regression: 126 passed.
- `reason ci --json`: PASS, 1034 tests.
- Agent Protocol: PASS.

- Implemented the Update Package Provenance and Freshness Verification
  Specification v0.1 (`reasonscript-update-package-manifest/1.0`):
  - `scripts/build_update_package.py` now records the source commit, dirty
    tree state, builder identity and hash, validation profile hash, and
    per-file payload hashes into a canonical
    `metadata/update_package_manifest.json` with a sidecar SHA-256, rejects
    release builds from dirty source trees, stages packages under
    `dist/.staging`, self-validates them with the install-side validator,
    and emits archive/manifest sidecar hashes.
  - `reason update` validates package provenance before staging or
    activation (INS-PROV-001..020 diagnostics), classifies package
    freshness (`fresh`/`stale`/`unknown`/`invalid`/`development`), rejects
    stale, dirty, development-class, and legacy (manifest-less) packages by
    default, and supports `--expected-commit`,
    `--allow-development-package`, and `--allow-legacy-package`.
  - Added `reason update package-inspect <archive>` and
    `reason update package-validate <archive>`.
  - Successful updates retain the package manifest and an installation
    record under `versions/<v>/metadata/`, write
    `reasonscript-update-transaction/1.1` artifacts under
    `metadata/transactions/`, and `reason install-info --json` reports the
    active package provenance; provenance survives rollback for every
    installed version.
  - Added `schemas/update_package_manifest.schema.json`
    (provenance manifest) and `schemas/update_transaction.schema.json`;
    the previous package-manifest schema moved to
    `schemas/install_manifest_v1_1.schema.json`.

## ReasonScript Dynamic ReasonUnit Cluster Execution v0.1 - 2026-07-18

### Status

VALIDATED

### Added

- Added the optional Rust Dynamic ReasonUnit Runtime under
  `ClusterRuntime/src/dynamic`.
- Added deterministic Dynamic Unit Proposal validation and canonical
  ReasonUnit ID generation.
- Added duplicate proposal and duplicate ReasonUnit elimination.
- Added Coordinator-owned lifecycle management with terminal-state protection.
- Added atomic, checksummed Dynamic Plan Revisions at logical-step and epoch
  boundaries.
- Added dynamic dependency validation and cyclic dependency rejection.
- Added declared state access, state proposal validation, conflict detection,
  and Coordinator-owned shared-state commits.
- Added bounded branch management, global and branch budgets, pruning, and
  explicit budget termination.
- Added suspension, reactivation, replacement, retirement, and worker-failure
  reassignment.
- Added quiescence, state stability, convergence evaluation, and convergence
  reporting.
- Added the `reason cluster dynamic` plan, simulate, run, validate, compare,
  and test-model commands through a thin Python CLI adapter.
- Added nine Dynamic ReasonUnit JSON Schemas.
- Added nine canonical Dynamic ReasonUnit artifacts and offline replay
  validation.
- Added DRU-TM-001 through DRU-TM-013 and molecular scenario DRU-TM-MOL-001.

### Validation

- Rust integration tests: PASS.
- Dynamic and molecular acceptance scenarios: 14/14 PASS.
- Dynamic CLI tests: 2 PASS.
- Dynamic artifact validation: 9/9 PASS.
- `reason ci --json`: PASS, 879 tests.
- `reason agent-protocol --json`: PASS, AP-001 through AP-010.
- Canonical agent report: COMPLETED.

### Compatibility

- ReasonScript grammar is unchanged.
- Reason IR semantics are unchanged.
- ExecutionPlan semantics are unchanged.
- Single-node Runtime behavior is unchanged.
- Static Cluster Runtime behavior is unchanged.
- Static Cluster Runtime canonical artifacts are unchanged.
- Python does not implement Dynamic Runtime semantics.

## ReasonScript Install Foundation v1.1 - 2026-07-14

### Added

- Added the cross-platform `reason update` CLI for package checks, local package updates, installed-state validation, and rollback.
- Added common install state, current-version, managed-file inventory, update-history, package checksum, and update-report contracts.
- Added deterministic version planning, SHA-256 verification, archive traversal protection, staging, version-directory installation, atomic activation, preservation, and rollback.
- Added macOS, Linux, and Windows Platform Adapter contracts plus a dependency-free native Rust activation helper.
- Added deterministic local update-package generation and bundled Phase 1R validation fixtures.

### Changed

- Updated ReasonScript from 0.5.0 to 0.5.1 so the update foundation ships as a distinct Release Unit.
- Updated clean installation to create v1.1 metadata while retaining the v1.0 root manifest and `current` compatibility entry.
- Updated the fixed launcher to resolve `metadata/current.json` and the active version's `bin/reason-runtime`.

### Validation

- Native updater unit test: PASS.
- Install/update regression tests: PASS.
- Installed `0.5.0 -> 0.5.1`, post-install validation, and explicit rollback lifecycle on macOS arm64: PASS.
- `reason ci --json`: PASS, 839 tests.
- Linux and Windows adapters are implemented and contract-tested; device validation remains pending.

## ReasonScript KDA-2 Component Validation v1.0

### Status

PROPOSED (specification); executed with result VALIDATED — see Execution Results below.

### Added

- Added the formal KDA-2 component-validation contract, Specification ID `reasonscript-kda2-component-validation/1.0`.
- Added installed-only Runtime provenance validation (KDA2-V1).
- Added Dataset, Feature, Rule, Prediction, Evidence, Evaluation, Knowledge, Visualization, Artifact, and Determinism validation phases (KDA2-V2 through KDA2-V13).
- Added `KDA2-CV-001` through `KDA2-CV-050`.
- Added explicit repository-wide CI failure classification (`kda2_related` / `unrelated` / `uncertain`).
- Added formal component-validation result and report contracts.

### Execution Results

- Acceptance criteria: 50 passed / 0 failed
- KDA-2 diagnostics: 0
- Determinism (full pipeline rerun, 416 files compared): PASS, 0 digest mismatches
- Installed-only import provenance: CONFIRMED, no `.deps` or core-repository source used
- KDA-1 regression, `reason doctor --json`, `reason install-validate --json`: PASS
- Repository-wide `./reason ci --json`: FAIL — `CI-008`, classified `unrelated`, does not block KDA-2 component status
- Final KDA-2 Component Status: **VALIDATED**

### Compatibility

- KDA-2 implementation semantics are unchanged.
- Titanic Rule Set v1.0 is unchanged.
- Data Foundation, VSL v0.1, and MLV v0.2 semantics are unchanged.
- Repository-wide certification remains separate from KDA-2 component validation.

## ReasonScript KDA-2 Titanic Rule-based Classification v1.0 Specification

### Status

VALIDATED (KDA-2 Component) — external consumer implementation exists; formal component validation executed and passed via `reasonscript-kda2-component-validation/1.0`.

### Added

- Added the initial formal specification for KDA-2 Titanic Rule-based Classification.
- Added Specification ID `reasonscript-kda2-titanic-rule-classification/1.0`.
- Defined the Dataset, Feature, Rule, Prediction, Decision Path, Evidence, Evaluation, Knowledge, Visualization, Artifact, Determinism, and Installed Distribution contracts.
- Added `KDA2-AC-001` through `KDA2-AC-050`.
- Defined strict installed-only Runtime provenance requirements.
- Separated KDA-2 component validation from repository-wide canonical CI reporting.
- Documented the external implementation and artifact location under the `kaggle-titanic-validation` project.

### Verified External Results

- Dataset rows: 891
- Feature records: 891
- Predictions: 891
- Prediction Evidence records: 891
- Accuracy: 0.7598204264870931
- Balanced accuracy: 0.777538107563992
- AUC: 0.8462755248777681
- Average precision: 0.7903496180334
- Knowledge records: 10
- Visualizations: 14
- Diagnostics: 0
- Repeated-run artifact digest equality: PASS
- KDA-1 regression: PASS

### Validation Status

- External KDA-2 implementation and artifacts: CONFIRMED
- Installed Distribution import provenance: CONFIRMED
- Formal KDA-2 component validation: PENDING
- Repository-wide canonical CI: FAIL — `CI-008 Test failure`
- Repository-wide failures are recorded separately and are not hidden.

### Compatibility

- No KDA-2 domain implementation was added to the ReasonScript Core repository.
- Data Analysis Foundation behavior is unchanged.
- Visualization Standard Library behavior is unchanged.
- ML Evaluation Visualization v0.2 behavior is unchanged.
- Reason IR, ExecutionPlan, Simulation, Knowledge, and Core CLI semantics are unchanged.

## Installed Distribution ML Evaluation v0.2 Correction

- Include the complete `runtime.visualization.evaluation` import closure and v0.2 schemas in installed-distribution validation.
- Record every ML Evaluation Python module in the install manifest under the `ml-evaluation-visualization-v0.2` component.
- Validate installed-only public API imports, repository isolation, Matplotlib-independent evaluation, JSON serialization, and canonical AUC/AP values.

## ReasonScript ML Evaluation Visualization Standard Library v0.2 - 2026-07-12

### Status

VALIDATED

### Added

- Added JSON-safe binary and multiclass classification evaluation models.
- Added confusion matrices, normalization, classification metrics, ROC/AUC, and precision–recall/AP.
- Added Rule coverage/accuracy, error distribution, Decision Path, confidence, and score visualizations.
- Added classification, metric, threshold, Rule, and Decision Path evidence.
- Added evaluation Visualization IR, Render Plan, JSON Schemas, Artifacts, and Manifest integration.
- Added installed external-project regressions.

### Compatibility

- Visualization v0.1 behavior remains unchanged and Matplotlib remains render-time optional.
- Evaluation and JSON Artifact generation require no Matplotlib.
- Data Foundation, Tensor functions, Reason IR, and non-visualization programs remain unchanged.

### Validation

- Binary and multiclass evaluation: PASS
- Confusion matrices, metrics, ROC/AUC, and precision–recall/AP: PASS
- Rule, Decision Path, error, confidence, and score evaluation: PASS
- PNG/SVG rendering and same-environment determinism: PASS
- Installed external-project regression: PASS
- Canonical `reason ci --json`: PASS (808 tests)

---

## ReasonScript Visualization Standard Library v0.1 - 2026-07-12

### Status

VALIDATED

### Added

- Added immutable backend-independent Visualization specifications under `runtime.visualization` (`visual.*`).
- Added basic and analytical chart constructors with Typed Table grouping, aggregation, correlation, and missingness.
- Added the optional Matplotlib reference backend with deterministic PNG/SVG rendering.
- Added Visualization IR, Render Plan, Evidence, Validation, JSON Schemas, and Artifact Manifest output.
- Added seven-chart Titanic and installed external-project regressions.

### Security and Resources

- Added project-root output confinement, path traversal rejection, explicit format and image limits, and lazy backend loading.

### Compatibility

- Matplotlib remains optional through `reasonscript[visualization]`; Core and Data Foundation behavior is unchanged when absent.

### Validation

- Basic and analytical chart contracts: PASS
- Matplotlib PNG/SVG rendering and same-environment determinism: PASS
- Titanic seven-chart regression and installed external-project rendering: PASS
- Canonical `reason ci --json`: PASS (804 tests)

---

## ReasonScript Data Analysis Public Result Serialization v1.0 - 2026-07-12

### Status

VALIDATED

### Added

- Added JSON-safe public data-analysis result envelopes and JSON Schemas.
- Added explicit public/internal Titanic analysis API separation.
- Added deterministic backend, table-summary, dataset, Knowledge, and Evidence serialization.
- Added optional `titanic_analysis_result.json` artifact support and serialization regressions.

### Fixed

- Fixed `analyze_titanic` leaking non-serializable `DataBackend` and `Table` instances.
- Fixed standard `json.dumps` persistence and public result determinism.

### Compatibility

- Titanic metrics, Knowledge count, and Data Analysis Foundation semantics remain unchanged.
- Runtime-context callers use `analyze_titanic_execution`.

### Validation

- Public result serialization, JSON Schema contract, and determinism: PASS
- Installed external-project Titanic regression: PASS
- Canonical `reason ci --json`: PASS (801 tests)

---

## ReasonScript Install Practical Validation Corrections v1.0 - 2026-07-11

### Status

VALIDATED

### Added

- Added `reason version-validate [--json]` and its version-validation schema.
- Added current release metadata consistency validation to canonical CI environment validation.
- Added package-identifier normalization and separate project name/identifier fields.
- Added project-configured artifact output resolution without requiring `--out`.
- Added atomic installed CLI smoke-state finalization and practical external-project regressions.

### Compatibility

- Explicit artifact `--out` remains supported and overrides project configuration.
- Existing projects are never rewritten implicitly.
- Runtime, parser, Reason IR, ExecutionPlan, Simulation, and Knowledge semantics are unchanged.

---

## ReasonScript Install Foundation v1.0 - 2026-07-11

### Status

VALIDATED

### Certification

- Repository validation: PASSED
- macOS local installation validation: PASSED
- Linux x86_64 release certification: PENDING CI runner validation
- Windows x86_64 release certification: PENDING CI runner validation

### Summary

ReasonScript Install Foundation v1.0 establishes the official installation,
environment validation, project initialization, manifest, integrity, and safe
uninstallation contracts for ReasonScript.

The foundation enables users and Coding Agents to install and validate
ReasonScript outside the source repository through a user-scoped installation
layout.

### Added

- Added `reason --version [--json]`.
- Added `reason doctor [--json]`.
- Added `reason install-info [--json]`.
- Added `reason install-validate [--json]`.
- Added `reason init <path> --template minimal`.
- Added macOS and Linux installation through `scripts/install.sh`.
- Added Windows installation through `scripts/install.ps1`.
- Added atomic version installation and activation.
- Added Install Manifest generation.
- Added SHA-256 file integrity records.
- Added source and `pipx` Python package entry points.
- Added Standard Library distribution resources.
- Added Install Foundation JSON Schemas.
- Added safe uninstall with dry-run and purge modes.
- Added platform-specific installation documentation.
- Added installation contract and end-to-end tests.

### Validation

- `reason ci --json`
  - PASSED
- Full test suite
  - 787 passed
- Golden Corpus
  - PASSED
- Phase 8 Golden
  - 6 scenarios passed
- Install Foundation tests
  - 4 passed
- Existing Toolchain conformance tests
  - 39 passed
- Temporary installation lifecycle
  - install: PASSED
  - CLI execution: PASSED
  - manifest validation: PASSED
  - uninstall: PASSED
  - residual file validation: PASSED

### Known Certification Gaps

- Linux x86_64 clean-runner release certification remains to be completed.
- Windows x86_64 clean-runner release certification remains to be completed.
- PyPI publication is not included in Install Foundation v1.0.
- Homebrew, winget, Scoop, Chocolatey, apt, and standalone binary distribution
  remain future distribution channels.

### Compatibility

- Existing repository-local `./reason` execution remains supported.
- Existing CLI behavior is preserved.
- Runtime semantics are unchanged.
- Parser semantics are unchanged.
- Existing Reason IR, ExecutionPlan, Simulation, Knowledge, and ReasoningModel
  contracts are unchanged.
- Optional ML and image-processing backends are not required for Core
  installation.

---

## ReasonScript IDE Phase 4-D - Cross-platform Policy, Tests, and Docs - 2026-07-01

### Status

VALIDATED

### Summary

ReasonScript IDE Phase 4-D has been completed as the Cross-platform Policy,
Tests, and Docs phase.

This phase consolidates the Phase 4 cross-platform adapter foundation. It fixes
the browser-first policy, desktop stub policy, final `PlatformAdapter` contract,
path policy, workspace/artifact adapter policy, command/shortcut policy,
settings persistence policy, notification policy, and desktop shell deferred
policy.

Phase 4-D is a stabilization phase. Parser behavior, runtime behavior,
Reason IR semantics, `/api/analyze`, and `/api/workspace/*` contracts remain
unchanged.

### Added

- Added Phase 4-D policy documentation:
  - `phase4_cross_platform_foundation.md`
  - `browser_desktop_boundary.md`
  - `platform_adapter_final_contract.md`
  - `phase4_policy_index.md`
  - `desktop_shell_deferred_policy.md`
- Added Phase 4 final policy index.
- Added Desktop Shell deferred policy.
- Added Phase 4-D integration tests:
  - platform foundation contract
  - no direct platform leakage
  - browser / desktop boundary
  - required policy docs

### Changed

- Clarified that `BrowserPlatformAdapter` is the official Phase 4 runtime
  target.
- Clarified that `DesktopPlatformAdapter` is only a future replacement point.
- Updated `DesktopPlatformAdapter` capability flags so native dialogs, native
  menus, local filesystem shell integration, and local process execution are not
  exposed in Phase 4-D.
- Clarified that desktop workspace and artifact operations return
  `PlatformErrorKind=unsupported` until a desktop shell provides real
  implementations.
- Updated existing platform adapter contract documentation.
- Updated changelog for Phase 4-D.

### Fixed

- Fixed Phase 4 policy boundary across:
  - `PlatformAdapter`
  - `WorkspaceAdapter`
  - `ArtifactAdapter`
  - `CommandAdapter`
  - `SettingsAdapter`
  - `NotificationAdapter`
- Fixed `NormalizedRelativePath` as the UI file identity policy.
- Fixed analyze-result backed `ArtifactAdapter` as the Phase 4 artifact policy.
- Fixed command-oriented shortcuts as the Phase 4 shortcut policy.
- Fixed Desktop Shell as deferred beyond Phase 4.

### Compatibility

- Existing Playground-first behavior is preserved.
- Phase 3 workspace editing behavior is preserved.
- Phase 3.5 standard layout behavior is preserved.
- Phase 4-A/B/C adapter behavior is preserved.
- `/api/analyze` contract is unchanged.
- `/api/workspace/list` contract is unchanged.
- `/api/workspace/read` contract is unchanged.
- `/api/workspace/save` contract is unchanged.
- Runtime semantics are unchanged.
- Parser behavior is unchanged.
- Desktop shell remains deferred.

### Validation

- `python3 -m pytest tests/ide/test_phase4_*.py -v --tb=short`
  - 23 passed
- `python3 -m pytest tests/ide -v --tb=short`
  - 141 passed
- `npm run build`
  - passed
- `python3 scripts/dev.py test ide`
  - 161 passed
- `python3 scripts/dev.py test smoke`
  - passed
- `python3 scripts/dev.py test backend`
  - 33 passed
- `git diff --check`
  - passed

---

## ReasonScript IDE Phase 4 - Cross-platform UI / Platform Adapter Foundation - 2026-07-01

### Status

VALIDATED

### Summary

ReasonScript IDE Phase 4 has been completed as the Cross-platform UI /
Platform Adapter Foundation.

This phase prepares the Playground-first IDE for future macOS, Windows, and
Linux desktop shell support by separating UI behavior from browser, desktop,
and OS-specific concerns.

Phase 4 does not implement the desktop shell. It establishes the adapter
architecture required for future desktop integration.

### Included Sub-phases

- Phase 4-A: Platform Adapter Core
- Phase 4-B: Workspace & Artifact Adapter Migration
- Phase 4-C: Command / Settings / Notification Adapter
- Phase 4-D: Cross-platform Policy, Tests, and Docs

### Added

- Added `PlatformAdapter`.
- Added `BrowserPlatformAdapter`.
- Added `DesktopPlatformAdapter` stub.
- Added `WorkspaceAdapter` operational boundary.
- Added `ArtifactAdapter` operational boundary.
- Added `CommandAdapter` and `CommandRegistry`.
- Added `SettingsAdapter` persistence.
- Added `NotificationAdapter`.
- Added `PlatformError` model.
- Added `NormalizedRelativePath` validation.
- Added command-oriented shortcut policy.
- Added browser / desktop boundary documentation.
- Added Desktop Shell deferred policy.
- Added Phase 4 integration tests.

### Final Architecture

```txt
UI Components
  -> CommandRegistry / UI State
  -> PlatformAdapter
      -> WorkspaceAdapter
      -> ArtifactAdapter
      -> CommandAdapter
      -> SettingsAdapter
      -> NotificationAdapter
  -> BrowserPlatformAdapter or future DesktopPlatformAdapter
```

### Final Policy

- `BrowserPlatformAdapter` is the official Phase 4 runtime target.
- `DesktopPlatformAdapter` is a future replacement point only.
- Desktop Shell implementation is deferred.
- UI file identity uses `NormalizedRelativePath`.
- Workspace operations go through `PlatformAdapter.workspace`.
- Artifact operations go through `PlatformAdapter.artifacts`.
- IDE actions are command-oriented through `IdeCommand`.
- Settings persist through `SettingsAdapter`.
- User-visible messages go through `NotificationAdapter`.
- Unsupported desktop operations return `PlatformErrorKind=unsupported`.

### Compatibility

- Existing Playground-first workflow is preserved.
- Existing workspace editing behavior is preserved.
- Existing standard IDE layout behavior is preserved.
- `/api/analyze` contract is unchanged.
- `/api/workspace/list` contract is unchanged.
- `/api/workspace/read` contract is unchanged.
- `/api/workspace/save` contract is unchanged.
- Runtime semantics are unchanged.
- Parser behavior is unchanged.
- Desktop shell remains deferred.

### Validation

- Phase 4-D focused tests passed.
- Full `tests/ide` passed.
- UI build passed.
- Official IDE tests passed.
- Smoke tests passed.
- Backend tests passed.
- `git diff --check` passed.

---

## ReasonScript IDE Phase 4-C - Command / Settings / Notification Adapter - 2026-07-01

### Status

VALIDATED

### Summary

ReasonScript IDE Phase 4-C has been completed as the Command / Settings /
Notification Adapter phase.

This phase adds a command-oriented action boundary for IDE operations,
introduces persistent browser settings through `SettingsAdapter`, and routes
user-visible messages through `NotificationAdapter`.

Top Bar actions, panel switching, and keyboard shortcut readiness now share the
same `IdeCommand` surface. This prepares the Playground-first IDE for future
desktop menu and OS-specific shortcut integration.

### Added

- Added expanded `IdeCommand` surface:
  - `openWorkspace`
  - `refreshWorkspace`
  - `saveFile`
  - `analyzeFile`
  - `runCurrentFile`
  - `validateWorkspace`
  - `auditProject`
  - `showOverview`
  - `showPlan`
  - `showSimulation`
  - `showKnowledge`
  - `showArtifacts`
  - `showProblems`
  - `showOutput`
  - `showLogs`
  - `showTests`
  - `clearOutput`
  - `clearNotifications`
- Added `CommandRequest`.
- Added `CommandResult`.
- Added `CommandRegistry`.
- Added shortcut binding table.
- Added command-oriented Top Bar actions.
- Added command-oriented Right Inspector tab switching.
- Added command-oriented Bottom Tool Window tab switching.
- Added browser `SettingsAdapter` persistence using `localStorage` with memory
  fallback.
- Added persistence for:
  - `compilerMode`
  - `rightInspector.activeTab`
  - `bottomToolWindow.activeTab`
- Added `NotificationAdapter` metadata support:
  - `title`
  - `operation`
  - `details`
  - `durationMs`
- Added `PlatformError` to notification severity mapping.
- Added Phase 4-C documentation and contract tests.

### Changed

- Save now routes through the `saveFile` command.
- Analyze now routes through the `analyzeFile` command.
- Run now routes through the `runCurrentFile` command.
- Validate now routes through the `validateWorkspace` command.
- Audit now routes through the `auditProject` command.
- Right Inspector tab selection now routes through command names.
- Bottom Tool Window tab selection now routes through command names.
- Browser settings now use `localStorage` with memory fallback.

### Keyboard Shortcut Policy

Shortcuts bind to `IdeCommand` names, not directly to UI handlers.

Initial bindings:

| Command | macOS | Windows | Linux |
| --- | --- | --- | --- |
| `saveFile` | `Cmd+S` | `Ctrl+S` | `Ctrl+S` |
| `analyzeFile` | `Cmd+Enter` | `Ctrl+Enter` | `Ctrl+Enter` |
| `showProblems` | `Cmd+Shift+M` | `Ctrl+Shift+M` | `Ctrl+Shift+M` |

Full OS-level shortcut binding remains outside Phase 4-C.

### Notification Policy

Notifications are platform-bound user messages with three levels:

- `info`
- `warning`
- `error`

Browser Phase 4-C uses console fallback notifications. Desktop native
notifications are deferred to the desktop shell phase.

### Compatibility

- Existing Playground behavior is preserved.
- Phase 4-B workspace/artifact adapter behavior is preserved.
- `/api/analyze` contract is unchanged.
- `/api/workspace/list` contract is unchanged.
- `/api/workspace/read` contract is unchanged.
- `/api/workspace/save` contract is unchanged.
- Runtime semantics are unchanged.
- Desktop shell remains deferred.

### Validation

- `npm run build`
- `python3 -m pytest tests/ide/test_command_adapter_contract.py tests/ide/test_command_registry.py tests/ide/test_settings_adapter_contract.py tests/ide/test_notification_adapter_contract.py tests/ide/test_shortcut_command_mapping.py -v --tb=short`
- `python3 scripts/dev.py test ide`
- `python3 scripts/dev.py test smoke`
- `python3 scripts/dev.py test backend`
- `git diff --check`

All validation commands passed.

---

## ReasonScript IDE Phase 4-B - Workspace & Artifact Adapter Migration - 2026-07-01

### Status

VALIDATED

### Summary

ReasonScript IDE Phase 4-B has been completed as the Workspace & Artifact
Adapter Migration phase.

This phase moves workspace list/read/save operations and artifact access behind
the `PlatformAdapter` boundary introduced in Phase 4-A. The browser
implementation continues to use the existing backend contracts, while UI
components no longer directly depend on workspace endpoints.

The phase also adds file-backed analyze path validation, analyze-result backed
artifact access, `PlatformError` mapping, and adapter path enforcement.

### Added

- Added operational `BrowserWorkspaceAdapter` support for workspace list,
  workspace file read, and workspace file save.
- Added analyze-result backed `BrowserArtifactAdapter`.
- Added artifact descriptors for `ast.json`, `semantic_ast.json`,
  `reason_ir.json`, `execution_plan.json`, `simulation.json`, `knowledge.json`,
  `diagnostics.json`, and `validation.json`.
- Added `PlatformError` mapping for workspace and artifact operations.
- Added path enforcement for workspace read/save and file-backed analyze.
- Added Phase 4-B documentation.
- Added Phase 4-B contract tests.

### Changed

- Moved workspace open/refresh through
  `PlatformAdapter.workspace.listWorkspace`.
- Moved file selection through `PlatformAdapter.workspace.readFile`.
- Moved save workflow through `PlatformAdapter.workspace.saveFile`.
- Removed direct bridge dependency from `WorkspaceExplorerView`.
- Moved Artifacts tab access through `PlatformAdapter.artifacts`.
- Added pre-validation for `source_context.relative_path` before file-backed
  analyze.
- Kept raw analyze response available through the fallback `All Raw` view.

### Platform Error Mapping

Workspace backend mappings:

| Backend code | PlatformErrorKind |
| --- | --- |
| `NOT_FOUND` | `missing` |
| `PATH_TRAVERSAL` | `path_traversal` |
| `PERMISSION_DENIED` | `permission_denied` |
| `DECODE_ERROR` | `invalid_encoding` |
| `INVALID_ENCODING` | `invalid_encoding` |
| `VERSION_CONFLICT` | `conflict` |
| `READ_ONLY` | `read_only` |

HTTP mappings:

| HTTP status | PlatformErrorKind |
| --- | --- |
| `404` | `missing` |
| `409` | `conflict` |
| other non-2xx | `network_error` |

Thrown fetch failures are returned as `network_error`. Unsupported desktop stub
operations return `unsupported`.

### Compatibility

- Existing Playground-first behavior is preserved.
- Phase 3 workspace editing behavior is preserved.
- Phase 3.5 standard layout behavior is preserved.
- `/api/analyze` contract is unchanged.
- `/api/workspace/list` contract is unchanged.
- `/api/workspace/read` contract is unchanged.
- `/api/workspace/save` contract is unchanged.
- Temporary source analyze mode remains supported.
- Desktop shell remains deferred.

### Validation

- `npm run build`
- `python3 -m pytest tests/ide/test_workspace_adapter_migration.py tests/ide/test_artifact_adapter_migration.py tests/ide/test_adapter_path_enforcement.py tests/ide/test_workspace_adapter_error_mapping.py -v --tb=short`
- `python3 scripts/dev.py test ide`
- `python3 scripts/dev.py test smoke`
- `python3 scripts/dev.py test backend`

All validation commands passed.

---

## ReasonScript IDE Phase 4-A - Platform Adapter Core - 2026-07-01

### Status

VALIDATED

### Summary

ReasonScript IDE Phase 4-A defines the Platform Adapter Core.

This phase introduces the minimum adapter layer required to prepare the
Playground-first IDE UI for future macOS, Windows, and Linux desktop support.
It does not implement a native desktop shell.

### Added

- Added `apps/reasonscript-ide/ui/src/platform/types.ts`.
- Added `PlatformAdapter`, `PlatformEnvironment`, `PlatformErrorKind`,
  `PlatformError`, and `NormalizedRelativePath`.
- Added minimal workspace, artifact, command, settings, and notification
  sub-adapter interfaces.
- Added `BrowserPlatformAdapter`.
- Added `DesktopPlatformAdapter` stub.
- Added active adapter resolver through `getPlatformAdapter()`.
- Added slash-normalized relative path validation.
- Added explicit unsupported operation error policy.
- Added Phase 4-A platform adapter tests and documentation.

### Non-Goals

- No Desktop shell implementation.
- No native file dialogs.
- No native menus.
- No packaging or installer work.
- No terminal emulator.
- No LSP integration.
- No runtime semantic changes.
- No `/api/analyze` contract changes.
- No workspace API contract changes.

### Compatibility

- Existing Playground workflow remains unchanged.
- Existing Phase 3 workspace editing behavior remains unchanged.
- Existing Phase 3.5 standard layout remains unchanged.
- Desktop support remains deferred.

---

## ReasonScript IDE Phase 3.5 - Standard IDE Layout Simplification - 2026-07-01

### Status

VALIDATED

### Summary

ReasonScript IDE Phase 3.5 has been completed as the Standard IDE Layout
Simplification phase.

This phase reorganizes the Playground-first IDE into a simpler Android
Studio-style layout with five major regions: Top Bar, Left Project Pane, Center
Editor, Right Inspector, and Bottom Tool Window.

The overloaded right-pane tab structure has been reduced to five primary tabs:
Overview, Plan, Simulation, Knowledge, and Artifacts. Operational feedback has
been moved into a Bottom Tool Window with Problems, Output, Logs, and Tests
tabs.

### Added

- Added Standard IDE Layout v0.2 implementation.
- Added Top Bar with Project, File, Mode, Validate, Run, Analyze, Audit, and
  Status.
- Added simplified Right Inspector tabs:
  - Overview
  - Plan
  - Simulation
  - Knowledge
  - Artifacts
- Added Bottom Tool Window tabs:
  - Problems
  - Output
  - Logs
  - Tests
- Added `StandardLayoutViews.tsx`.
- Added Phase 3.5 layout contract tests.
- Added Phase 3.5 development documentation:
  - `standard_ide_layout.md`
  - bottom tool window contract
  - cross-platform UI readiness
  - layout migration map

### Changed

- Consolidated Pipeline and Summary into Overview.
- Moved detailed diagnostics to Bottom Problems.
- Moved runtime output to Bottom Output.
- Moved AST, Semantic AST, Reason IR, Validation, and Raw JSON into Artifacts.
- Moved ExecutionPlan into Plan.
- Moved Simulation, Runtime, Input, and Trace information into Simulation.
- Moved Knowledge and evidence information into Knowledge.
- Reclassified Diff, Regression, Baseline, and related outputs toward Bottom
  Tests or future Audit sections.
- Preserved existing functionality through relocation, grouping, and collapsible
  detail sections.

### Cross-platform Readiness

- The five-region layout is compatible with browser and future desktop shell
  embedding.
- UI logic does not depend on OS-specific path separators.
- `relative_path` values are treated as slash-normalized display paths.
- Keyboard shortcuts remain command-oriented for future desktop menu bindings.
- Right Inspector and Bottom Tool Window are compatible with future resizable
  panes.
- Native menus, native file dialogs, packaging, and installers remain outside
  Phase 3.5.

### Validation

- `python3 scripts/dev.py test ide`
  - 104 passed
- `python3 -m pytest tests/ide/test_standard_layout_contract.py -v --tb=short`
  - 4 passed
- `npm run build` in `apps/reasonscript-ide/ui`
  - passed

### Compatibility

- Parser behavior is unchanged.
- Runtime behavior is unchanged.
- Reason IR semantics are unchanged.
- ExecutionPlan semantics are unchanged.
- Simulation semantics are unchanged.
- Knowledge semantics are unchanged.
- `/api/analyze` contract is unchanged.
- Workspace list/read/save contracts are unchanged.
- Phase 3 workspace editing behavior is unchanged.
- Phase 3.5 changes are UI layout and information architecture changes only.

---

## ReasonScript IDE Phase 3 - Local Workspace Editing Foundation - 2026-07-01

### Status

VALIDATED

### Summary

ReasonScript IDE Phase 3 defines the Local Workspace Editing Foundation.

This phase extends the Playground-first IDE from temporary source editing
to workspace file-based development. It introduces selected file state,
editor binding, dirty state tracking, save workflow, analyze-current-file
workflow, per-file diagnostics, and per-file artifact identity. Runtime and
compiler semantics are unchanged — Phase 3 only changes how source text
reaches `/api/analyze`.

### Scope

- Workspace file selection
- Source editor binding
- File read / save
- Dirty state tracking
- Analyze selected file
- Per-file analyze result binding
- Per-file diagnostics
- Per-file artifact identity
- Missing file handling
- Path traversal protection
- Workspace editing documentation
- Workspace editing contract tests

### Non-Goals

- Desktop IDE full implementation
- Terminal emulator
- Full LSP integration
- Multi-file semantic linking
- Package manager
- Git integration
- Advanced runtime replay
- Cloud workspace

### Added

- Added `playground/backend/workspace.py`: workspace scan, read, save, and
  path-safety helpers.
- Added `POST /api/workspace/list` (also serves workspace refresh).
- Added `POST /api/workspace/read`.
- Added `POST /api/workspace/save`.
- Added optional `source_context` field to the `/api/analyze` request
  (`workspace_root`, `relative_path`, `dirty`) — omitting it preserves the
  exact Phase 2 behavior.
- Added `source_context` (with a deterministic `artifact_id`) to the
  `/api/analyze` response when a workspace file was analyzed.
- Added `relative_path` stamping on diagnostics when `source_context` is
  present.
- Added best-effort per-file artifact persistence under
  `<workspace_root>/.reasonscript/artifacts/<artifact_id>/`, reusing the
  existing Phase 2 artifact file names.
- Added `WorkspaceExplorer` sidebar to the Playground frontend: open a
  workspace root, browse the file tree, select a `.rsn`/`.reason` file.
- Added file-aware Source Editor: selected-file header (filename, dirty
  indicator, read-only/missing/stale badges), Save action, and a
  file-bound Analyze action.
- Added per-file analyze result cache in the frontend so switching files
  restores that file's last analyze result.
- Added Phase 3 development documentation:
  `workspace_editing_foundation.md`, `file_operation_contract.md`,
  `editor_state_contract.md`, `per_file_artifact_contract.md`,
  `per_file_diagnostics_contract.md`.
- Added workspace contract tests under `tests/ide/`.

### Required File Operations

- `list_workspace_files` — `POST /api/workspace/list`
- `read_workspace_file` — `POST /api/workspace/read`
- `save_workspace_file` — `POST /api/workspace/save`
- `refresh_workspace` — re-invoke `POST /api/workspace/list`
- `select_workspace_file` — frontend-only state; no backend endpoint (the
  backend is stateless per-request)

### Source File Extensions

- `.rsn` as preferred ReasonScript source extension
- `.reason` as optional compatibility extension

### Analyze Request Extension

`POST /api/analyze` may include optional `source_context`:

```json
{
  "source": "model Test {}",
  "compiler_mode": "default",
  "source_context": {
    "workspace_root": "/path/to/project",
    "relative_path": "examples/test.rsn",
    "dirty": false
  }
}
```

### Artifact Identity

Per-file artifacts use a deterministic source-path hash:

```
.reasonscript/artifacts/<artifact_id>/
```

where `artifact_id = sha256(relative_path)[:16]`. Required artifact names
remain unchanged: `ast.json`, `semantic_ast.json`, `reason_ir.json`,
`execution_plan.json`, `simulation.json`, `knowledge.json`,
`diagnostics.json`, `validation.json`.

### Acceptance Criteria

- Workspace file tree can select ReasonScript source files.
- Selected file content loads into Source Editor.
- Dirty state is tracked.
- Selected file can be saved.
- Path traversal is rejected.
- Selected file can be analyzed through `/api/analyze`.
- Analyze result is bound to selected file.
- Runtime panels display selected file analyze result.
- Diagnostics are associated with selected file.
- Missing selected file does not crash the IDE.
- Artifact identity is deterministic per file.
- Temporary source analyze mode remains supported.

### Validation

```
python3 scripts/dev.py test ide
python3 scripts/dev.py test backend
python3 scripts/dev.py test smoke
npm run build (playground/frontend)
```

### Compatibility

- Parser behavior is unchanged.
- Runtime behavior is unchanged.
- Reason IR semantics are unchanged.
- ExecutionPlan semantics are unchanged.
- Simulation semantics are unchanged.
- Knowledge semantics are unchanged.
- `/api/analyze` remains backward compatible with the Phase 2 request
  shape.
- `source_context` is optional.
- Temporary source analyze mode remains supported.

---

## ReasonScript IDE Phase 2 - Playground-first IDE Runtime Integration - 2026-06-29

### Status

VALIDATED

### Summary

ReasonScript IDE Phase 2 has been completed as the official
Playground-first Runtime Integration layer.

The Playground IDE now treats `POST /api/analyze` as the primary contract
endpoint for Source -> Surface AST -> Semantic AST -> Reason IR ->
ExecutionPlan -> Simulation -> Knowledge -> Diagnostics inspection.

The analyze response now returns a deterministic payload containing pipeline
status, runtime artifacts, structured view data, diagnostics, and compiler
mode.

### Added

- Added stabilized `/api/analyze` response contract.
- Added fixed pipeline stage ids:
  - `source`
  - `surface_ast`
  - `semantic_ast`
  - `reason_ir`
  - `execution_plan`
  - `simulation`
  - `knowledge`
  - `diagnostics`
- Added fixed stage status values:
  - `success`
  - `warning`
  - `error`
  - `skipped`
  - `unavailable`
- Added artifact state handling.
- Added diagnostics-to-pipeline stage mapping.
- Added Pipeline Overview tab to the Playground frontend.
- Added shared analyze result state for runtime artifact display.
- Added structured display integration for ExecutionPlan, Simulation,
  Knowledge, Diagnostics, and Runtime IO.
- Added Desktop-compatible ViewModel status updates.
- Added Phase 2 development documentation.
- Added `/api/analyze` contract test.

### Fixed

- Stabilized missing artifact handling.
- Ensured missing artifacts render as empty, skipped, or unavailable states.
- Prevented missing artifacts from crashing the IDE.
- Normalized diagnostic severity to `error`, `warning`, or `info`.
- Classified unknown diagnostics under the `diagnostics` stage.

### Analyze API Contract

`POST /api/analyze` accepts:

```json
{
  "source": "module Test { calculation Value { result = 42 } }",
  "compiler_mode": "default"
}
```

The response contains:

```json
{
  "ok": true,
  "compiler_mode": "default",
  "pipeline": {
    "stages": []
  },
  "artifacts": {},
  "views": {},
  "diagnostics": []
}
```

Required pipeline stages:

- `source`
- `surface_ast`
- `semantic_ast`
- `reason_ir`
- `execution_plan`
- `simulation`
- `knowledge`
- `diagnostics`

Required artifact names:

- `ast.json`
- `semantic_ast.json`
- `reason_ir.json`
- `execution_plan.json`
- `simulation.json`
- `knowledge.json`
- `diagnostics.json`
- `validation.json`

Every diagnostic returned by `/api/analyze` includes `code`, `message`,
`severity`, `stage`, and `source_range`. Unknown diagnostics are classified
under the `diagnostics` stage.

### Validation

- `python3 scripts/dev.py test smoke`
- `python3 scripts/dev.py test backend`
- `python3 scripts/dev.py test ide`
- `npm run build` in `playground/frontend`
- `npm run build` in `apps/reasonscript-ide/ui`

All validation commands passed.

### Compatibility

- Parser behavior is unchanged.
- Runtime behavior is unchanged.
- Reason IR semantics are unchanged.
- ExecutionPlan semantics are unchanged.
- Simulation semantics are unchanged.
- Knowledge semantics are unchanged.
- Phase 2 only stabilizes Playground IDE runtime integration.

### Positioning

```text
Phase 1:
  Development Environment
  Status: VALIDATED

Phase 2:
  Playground-first IDE Runtime Integration
  Status: VALIDATED

Next:
  Phase 3 candidate selection
```

## ReasonScript Language Layer v0.6-D - 2026-06-29

### Added

- Added Human Surface top-level construct policy.
- Defined `model` as active preferred syntax.
- Defined `module` as active compatibility syntax.
- Reserved `world` for WorldModel / simulation-domain syntax.
- Reserved `system` for multi-model orchestration syntax.
- Reserved `component` for UI / SDK structural composition syntax.
- Added reserved top-level construct diagnostic policy.

### Fixed

- Clarified that reserved top-level constructs must not silently parse as `model` or `module`.
- Clarified that `source_kind` remains L1/L7 metadata unless a future specification defines distinct core semantics.
- Preserved module/model L3-L6 equivalence guarantees from v0.6-B.

### Validation

- model active preferred syntax policy verified.
- module active compatibility syntax policy verified.
- reserved construct diagnostics verified.
- module/model core non-regression verified.
- top-level construct projection policy verified.
- Playground frontend build verified.

## ReasonScript Language Layer v0.6-C - 2026-06-29

### Added

- Added L7 Developer Projection support for `source_kind`.
- Added Playground Summary View presentation for `model` and `module`.
- Displayed `model` as preferred Human Surface syntax.
- Displayed `module` as compatibility syntax.
- Displayed normalized ReasonGraph target for top-level constructs.
- Added Diagnostics View support for `diagnostics.json`.

### Fixed

- Clarified that source spelling differences are projection metadata, not Reason IR semantics.
- Prevented Developer Projection from implying different core semantics for `module` and `model`.

### Validation

- Source kind projection verified.
- model preferred syntax projection verified.
- module compatibility syntax projection verified.
- Diagnostics artifact consumption verified.
- L3-L6 non-regression verified.
- Playground frontend build verified.

## ReasonScript Language Layer v0.6-B - 2026-06-28

### Added

- Accepted `model Example { ... }` as a top-level Human Surface alias.
- Added `source_kind` to Surface AST to preserve original top-level spelling.
- Added module/model equivalence validation across Reason IR, ExecutionPlan,
  Simulation, and Knowledge.
- Added `diagnostics.json` to Playground pipeline artifact export.

### Fixed

- Clarified that Human Surface spelling must not affect Reason IR semantics.
- Strengthened CI/CD coverage for Language Layer artifact consistency.

### Validation

- Surface AST source_kind distinction verified.
- Reason IR equivalence verified.
- ExecutionPlan equivalence verified.
- Simulation and Knowledge equivalence verified.
- Playground artifact contract verified.

## reasonscript-language-surface/0.5 - 2026-06-28

ReasonScript Language Surface v0.5 feature freeze.

### Frozen Surface

- Module system, declarations, type system, expressions, and statements
- Literal, enum, optional, struct, nested struct, guard, OR, and range patterns
- Source -> Surface AST -> Semantic AST -> Reason IR -> ExecutionPlan ->
  Simulation -> Knowledge pipeline
- Pattern Identity, canonical path generation, and branch evidence propagation

### Fixed Interfaces

- `reasonscript-language-surface/0.5`
- `parser/0.5`
- `reasonscript-ast/0.5`
- `reason-ir/0.5`
- `execution-plan/0.5`

### Compatibility Policy

- `0.5.x` releases may include bug fixes, diagnostics, compiler optimizations,
  and performance improvements.
- Syntax, semantic meaning, IR schema, canonical path generation, and Pattern
  Identity are frozen for the v0.5 line.
- New language features are deferred to v0.6.

## reasonscript-semantic-language/0.2 - 2026-06-15

ReasonScript Semantic Language v0.2 Core freeze.

### Frozen Core

- SemanticUnit and the seven adopted SemanticUnit types
- SemanticRelation and the eight core relation types
- SCV-1 structural validation
- Reasoning Space and SemanticPlan
- deterministic SemanticSimulation and SimulationResult
- validated Knowledge emergence with complete evidence

### Guarantees

- deterministic reasoning for identical graph, plan, and constraints
- SCV-1 enforcement throughout the reasoning pipeline
- immutable Reasoning Space during simulation
- trace, evidence, and confidence preservation
- reproducible SimulationResult and Knowledge JSON

### Out of Scope

- SCV-2 through SCV-5
- Knowledge repositories, persistence, retrieval, and re-reasoning
- MemorySpace, WorldModel, natural language parsing, and external execution

## reasonscript-language-surface/0.1 - 2026-06-14

ReasonScript Language Surface v0.1 release.

### Released

- Deterministic Source -> Surface AST -> Semantic AST -> Reason IR ->
  ExecutionPlan pipeline
- Module namespaces, imports, aliases, visibility, and qualified names
- Declarations, relations, expressions, patterns, statements, and Calculations
- Primitive and Reason State type annotations as validation contracts
- Canonical `node_type` serialization and round-trip compatibility
- Fixed AST, expression, pattern, statement, Calculation, type, and namespace
  validation families

### Fixed Interfaces

- `reasonscript-language-surface/0.1`
- `reasonscript-ast/0.1`
- `parser/0.1`
- `compiler/0.1`
- `reason-ir/0.1`
- `execution-plan/0.1`
- `reasonscript-calculation-semantics/0.1`

## 0.1.0-alpha - 2026-06-13

First integrated ReasonScript Platform alpha release.

### Added

- State-first layered Hybrid Runtime and transaction model
- Versioned `reason-ir/0.1` JSON ABI
- Common DTO declarations for Rust, Python, TypeScript, Go, and Java
- Five-layer platform conformance framework
- Versioned `reasonscript-ast/0.1` semantic AST ABI
- Deterministic `parser/0.1` Source-to-AST contract
- Deterministic `compiler/0.1` AST-to-Reason-IR contract
- End-to-end Source -> AST -> Reason IR -> Runtime validation

### Fixed Interfaces

- `reason-ir/0.1`
- `reasonscript-ast/0.1`
- `parser/0.1`
- `compiler/0.1`
- `transaction/0.1`
- `common-dto/0.1`
- `conformance-framework/0.1`

### Known Limitations

- The user-facing syntax remains experimental.
- Macros, language server, formatter, optimizer, distributed Runtime,
  persistence, and event sourcing are not included.
- Go conformance was not executed in the release environment because the Go
  toolchain was unavailable.
- Java DTO declarations compile, but a Java JSON codec adapter is not included.
- Full five-language SDK compatibility certification is not granted.
# Install Distribution Completeness v1.0

## Added

- Added the Playground backend and complete runtime import closure to the required distribution.
- Added repository-independent installed CLI and generated-project E2E validation.
- Added complete component inventory, entry-point integrity records, and project-name normalization.

## Fixed

- Fixed installed `reason check` failing with `ModuleNotFoundError: playground`.
- Fixed install validation accepting incomplete or repository-dependent distributions.
- Fixed relative source and artifact paths resolving against the installed distribution root.
