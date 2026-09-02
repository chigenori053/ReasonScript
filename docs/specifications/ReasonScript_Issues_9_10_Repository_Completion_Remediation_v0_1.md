# ReasonScript Issues #9 / #10 Repository Completion Remediation v0.1

Status: VALIDATED
Scope: repository implementation and validation
Issues: [#9](https://github.com/chigenori053/ReasonScript/issues/9),
[#10](https://github.com/chigenori053/ReasonScript/issues/10)
Distribution status: DEFERRED by scope decision

## 1. Purpose

This specification defines the remaining work required to:

1. make the Tensor call-frame liveness correction for Issue #9 safe,
   reproducible, and internally consistent; and
2. complete the remaining Unified Execution Runtime Architecture v0.1 work
   tracked by Epic #10 and produce evidence sufficient to close the Epic.

This increment ends at a clean, committed, pushed, and repository-validated
source state. Building a new install package, updating `~/.reasonscript`, and
proving the correction in an installed distribution are explicitly deferred.

The repository MUST NOT claim that an installed ReasonScript release contains
this work until the deferred distribution task is completed.

## 2. Current-state correction

### 2.1 Issue #9

The current source-tree implementation makes the original LayerNorm-to-attention
program succeed in the Rust computation VM. The implementation report and
committed test assets do not yet satisfy the specification:

- the fixture described as the "exact Issue #9 regression" is a reduced
  LayerNorm-plus-linear program rather than the Issue body verbatim;
- bounded recursion, error-unwind cleanup, trace-on/trace-off parity, cyclic
  containers, and actual cross-calculation Tensor retention are not covered;
- the active-frame implementation stores raw pointers to mutable runtime
  environments and reconstructs shared references in `unsafe` code; and
- the specification and report say `VALIDATED` even though the implementation,
  fixture, tests, and reports are not committed and pushed, and the required
  acceptance matrix is incomplete.

The Issue #9 documents MUST use `IN_PROGRESS` until every repository acceptance
criterion in this specification passes. A passing reduced fixture or a passing
local debug binary alone is insufficient.

### 2.2 Epic #10

The GitHub Epic body dated 2026-08-28 is stale. The current issue states are:

| Issue | Current state | Required treatment |
| --- | --- | --- |
| #11–#17 | Closed | Revalidate through the final UERA matrix; do not reimplement without evidence of regression. |
| #18 | Open | Complete Pure Function fast path and IR optimization acceptance. |
| #19 | Open | Complete parenthesized multiline-expression acceptance. |
| #20 | Closed | Re-run its final matrix after #18 and #19; its dependency gate was not satisfied when it closed. |
| #10 | Open | Close only after all gates in this specification pass. |

The final Epic report MUST use current commit IDs and issue states. Historical
commit `0fa7561` and the stale "implementation in progress" table MUST NOT be
presented as the final state.

## 3. Track A — Issue #9 Tensor lifetime remediation

### 3.1 Safe active-root representation

The Rust VM MUST compute Tensor roots from all active frames, retained
calculation results, expression temporaries, return/result handoffs, and native
autograd state as defined by
`ReasonScript_Tensor_Call_Frame_Liveness_Remediation_v0_1.md`.

The final design MUST NOT depend on dereferencing raw pointers to mutable
`HashMap` or `Vec` environments. Rust lifetimes, ownership, and aliasing safety
MUST be represented by safe types. Acceptable designs include:

- heap-stable frame objects owned through `Rc<RefCell<...>>` with all access
  mediated by the same safe ownership model; or
- owned per-frame Tensor-root sets refreshed at defined safe points and stacked
  independently of environment addresses.

An alternative safe design is permitted if it has no `unsafe` environment
dereference and passes the same observable contract.

RAII or an equivalent structured mechanism MUST remove frame and temporary roots
on normal return, `?` error propagation, trap, loop-limit exit, and call-depth
failure. Cleanup MUST neither leak roots nor collect a value that remains live
in an outer frame.

### 3.2 Exact canonical reproduction

The committed canonical fixture MUST be derived from the Issue #9 body without
reducing the Tensor chain. Only the package version and fixture-identification
metadata MAY change. It MUST retain:

- `tensor.random_normal([16, 32], ...)` for the input;
- 32-element `gamma` and `beta`;
- a `[32, 32]` query weight and `[16, 16]` bias;
- `tensor.mean`, `subtract`, `power`, `sqrt`, `divide`, `multiply`, and `add`
  in the LayerNorm-style function; and
- `linear`, `narrow`, `transpose`, `matmul`, `divide`, `add`, `softmax`, and
  final `matmul` in the attention-style caller chain.

The final result MUST assert shape `[16, 16]`. The regression test MUST load or
share the canonical fixture source instead of maintaining a reduced duplicate
under a misleading "exact" name.

### 3.3 Required lifetime tests

The committed test suite MUST cover all of the following:

1. the exact Issue #9 fixture through the native Rust host;
2. a Tensor referenced only by a suspended caller frame;
3. direct, nested-expression, array-contained, and struct-contained return
   values across at least one subsequent collection safe point;
4. at least three nested active frames;
5. a bounded recursive call preserving an outer caller-only Tensor;
6. argument lists where an earlier evaluated Tensor must survive a later
   user-function argument evaluation;
7. cleanup after normal return and cleanup after a runtime error;
8. trace disabled and enabled with identical result and error behavior;
9. shared and cyclic supported containers without unbounded traversal;
10. an earlier calculation returning an actual Tensor handle that is consumed
    by a later calculation;
11. 1,100 or more overwrite iterations demonstrating incremental reclamation;
12. explicit proof that unreachable intermediates are removed; and
13. genuine `max_live_tensors` exhaustion continuing to emit `TSF-013`.

A test that converts a calculation result with `tensor.to_array` before the next
calculation does not test cross-calculation Tensor retention.

Focused tests MUST fail rather than skip when the native runtime host is a
required build artifact. Optional local convenience runs MAY skip, but the
canonical validation path MUST build the host first.

### 3.4 Diagnostics and compatibility

- Valid active-frame Tensors MUST never emit `TSF-001`.
- A genuinely missing handle MUST continue to emit `TSF-001`.
- Genuine live-value exhaustion MUST continue to emit `TSF-013`.
- Source syntax, Computation IR schema, Tensor manifest, Tensor IDs, RNG,
  numerical mode, and public diagnostics MUST not drift unintentionally.
- Production execution MUST remain Rust-only with no Python fallback.
- Trace enablement MUST not change lifetime or collection decisions.

### 3.5 Issue #9 repository completion gate

Issue #9 MAY be closed as fixed in the repository when:

1. the safe implementation and all required assets are committed and pushed;
2. the exact fixture succeeds with `integrated-rust` /
   `rust_computation_vm` and result `true`;
3. `reason project-validate` passes runtime, artifact, golden, and three-run
   determinism validation for the exact fixture;
4. every test in section 3.3 passes;
5. Tensor and runtime-consolidation manifests show no unintended drift;
6. the canonical repository validation in section 6 passes; and
7. the Issue comment and completion report state explicitly that distribution
   packaging and installed-runtime verification are deferred.

Closing Issue #9 under this gate means "fixed and validated in the repository",
not "available in an installed release".

## 4. Track B — Epic #10 remaining implementation

### 4.1 Issue #18: Pure Function fast path and IR optimization

Issue #18 MUST implement and document:

- conservative `PureReasonFunction` classification excluding I/O, artifact
  writes, external state, global or mutable-state effects, nondeterminism, and
  observation dependencies;
- inlining only for pure, non-recursive functions with
  `instruction_count <= 32`;
- constant folding that preserves ReasonScript numerical and diagnostic
  semantics;
- loop-invariant code motion only when dependencies, mutation, observation,
  traps, and side effects prove the move safe; and
- a reproducible Relation Matrix performance fixture with stored profile and
  benchmark evidence.

Unknown purity MUST mean "not eligible". Optimization enabled and disabled MUST
produce identical results, diagnostics, traces where contractually observable,
and deterministic artifacts.

The Relation Matrix fixture MUST meet `<= 1.5 sec`, or record a reproducible
profile explaining the remaining gap and an explicit acceptance decision. A
silent performance miss is a failure.

### 4.2 Issue #19: parenthesized multiline expressions

Issue #19 MUST formally support newlines inside an explicitly parenthesized
expression while preserving the meaning of the corresponding single-line AST.
Implicit continuation outside parentheses remains out of scope.

Tests MUST cover:

- a basic multiline arithmetic expression;
- nested parentheses;
- multiline function-call arguments;
- arrays, indexing, and member/call combinations where currently supported;
- blank lines and line comments inside the parenthesized region;
- an unmatched opening parenthesis;
- an unexpected closing parenthesis;
- an incomplete operator expression;
- accurate one-based source location for invalid syntax; and
- the complete existing parser, semantic, lowering, and execution regressions.

Passing one basic multiline probe is insufficient to close Issue #19.

### 4.3 Issue #20 post-dependency revalidation

After #18 and #19 are completed, the full UERA-T001–T025 matrix MUST be executed
again from the final candidate commit. The matrix document MUST map every test
ID to:

- source fixture and command;
- expected backend and placement decision;
- expected result, diagnostics, trace, and artifact behavior;
- determinism comparison policy; and
- recorded pass/fail evidence.

The rerun MUST include existing ReasonScript regressions, ClusterRuntime,
Transformer basic training, autograd, optimizer, Relation Matrix, Sparse
Routing, Small/Medium/Large/Overload placement, and Local/Cluster comparison.
Required three-run byte-identical checks MUST be performed after optimization
and parser changes, not reused from the earlier #20 closure.

Issue #20 MAY either be reopened for this work or retain its closed state with a
new post-dependency validation report. In either case, #10 cannot close without
the new evidence.

### 4.4 Epic #10 reconciliation

The Epic body and completion report MUST be updated to show:

- #11–#17 as completed and revalidated;
- #18 and #19 as completed only after their own acceptance gates pass;
- #20 as post-dependency revalidated;
- the final candidate commit and validation date;
- UERA-T001–T025 evidence locations;
- remaining v0.1 non-goals; and
- deferred distribution work separately from repository completion.

Epic #10 MUST be the last issue closed in this sequence.

## 5. Documentation and report consistency

Before either Issue is closed:

1. Issue #9 specification and implementation report statuses MUST match the
   actual task state;
2. the report MUST not call a reduced fixture the exact Issue reproduction;
3. commands in reports MUST match the actual working directories and paths;
4. tested ReasonScript, Runtime, Rust toolchain, Python, OS, and architecture
   versions MUST be recorded;
5. test counts MUST distinguish Rust unit tests, focused top-level Python tests,
   `tests/`, and the full platform runner;
6. skipped tests and their reasons MUST be reported;
7. generated artifacts MUST be produced only by official commands and validate;
8. every completion claim MUST identify the commit containing the evidence; and
9. installed v0.5.5.5 MUST be documented as still unfixed until the deferred
   distribution task is completed.

## 6. Canonical validation sequence

Validation MUST run from a clean candidate checkout in this order:

1. build and test the complete `ReasonRuntime` Cargo workspace;
2. run Issue #9 focused lifetime tests with the freshly built host;
3. run #18 optimizer and performance tests with optimization on and off;
4. run #19 parser/diagnostic/lowering/execution tests;
5. run UERA-T001–T025 and three independent determinism runs;
6. run `reason workspace`;
7. run diagnostics and source checks for canonical fixtures;
8. generate and validate required artifacts;
9. run golden tests without automatically updating a failed baseline;
10. run Tensor and runtime-consolidation manifest checks;
11. run `python3 scripts/test_platform.py test` so Rust workspaces and test
    directories outside `tests/` are included;
12. run the canonical `reason ci`; and
13. confirm `git status --porcelain` is empty and local HEAD equals its upstream
    after commit and push.

No task may be reported `VALIDATED` based only on `reason ci` if its focused
tests live outside the `tests/` directory or require a separately built Rust
host.

## 7. Closure order

The required closure order is:

1. complete, validate, commit, and push Track A;
2. close #9 with a repository-only/deferred-distribution note;
3. complete and close #18;
4. complete and close #19;
5. perform and record #20 post-dependency revalidation;
6. reconcile the #10 body and completion report; and
7. close #10 last.

If any gate fails, the corresponding Issue remains open. Golden baselines MUST
NOT be updated solely to turn a failure into a pass.

## 8. Explicitly deferred distribution work

This increment MUST NOT:

- assign a new ReasonScript release version;
- build or publish an install archive;
- modify the Install Foundation installation;
- update `~/.reasonscript`;
- claim that the installed `reason` command contains the fix; or
- use installed-package success as a repository acceptance requirement.

A later distribution task MUST select a release version, build and verify the
package, update-install it locally, repeat the exact Issue #9 reproduction using
the installed binary, record provenance and hashes, and publish its own release
report.

## 9. Non-goals

The following remain outside this remediation:

- arbitrary instruction-level migration;
- GPU/CUDA cluster execution;
- remote or cloud cluster support;
- distributed optimizer state;
- JIT or bytecode VM introduction;
- new public Tensor garbage-collection controls;
- Tensor ID reuse or arena compaction; and
- unrelated language or runtime performance work.

## 10. Completion report

The final report MUST contain:

- completion summary for Tracks A and B;
- safe Tensor root-management design;
- exact Issue #9 results and lifetime/reclamation evidence;
- #18 purity, optimization, and performance evidence;
- #19 grammar and diagnostic evidence;
- UERA-T001–T025 post-dependency evidence;
- Rust, platform, CI, artifact, golden, and manifest results;
- commit and upstream synchronization evidence;
- compatibility notes;
- the explicit distribution deferral; and
- remaining work and non-goals.
