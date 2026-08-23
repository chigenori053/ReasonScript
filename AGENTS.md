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
