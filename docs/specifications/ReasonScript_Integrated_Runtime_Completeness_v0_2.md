# ReasonScript Integrated Runtime Completeness v0.2

Status: VALIDATED
Date: 2026-07-23

## Purpose

This remediation makes `reason run` the authoritative numerical execution
path. `reason object` remains the authoritative interface for validating,
loading, inspecting, querying, projecting, snapshotting, and saving canonical
ReasonUnit Objects; it is not a numerical physics evaluator.

## Required behavior

1. A scalar-only executable `calculation` is dispatched to the integrated
   runtime without requiring a loop, Tensor call, or Vision call.
2. The integrated runtime evaluates array indexing and index assignment,
   user-defined function calls, struct literals, member access, and mutable
   struct fields.
3. Executable programs may accumulate a deterministic array of frames and
   return the complete series from one `reason run`.
4. `reason run --result-output PATH` atomically writes only the finite,
   JSON-compatible runtime result.
5. Runtime failures use stable diagnostics for invalid indexes, calls, fields,
   recursion/call limits, and non-JSON output.
6. Symbolic fallback is explicit in the run result. It must not silently look
   like a successful numerical execution.

## Native ReasonUnit distribution

Source and packaged installations include the safe-Rust
`reasonunit-runtime-native` executable. Runtime lookup first checks the
installed `bin` directory and then repository release/debug development
locations. Staged distribution validation runs `verify-native`.

## Object CLI contract

- `reason object check SOURCE.rsn` validates ReasonScript source bindings.
- `reason object run SOURCE.rsn --allow-read` loads bound Objects.
- `inspect`, `query`, `snapshot`, `project`, `tensor`, and related Object
  operations accept canonical `.ruo` input.
- `NOT_EVALUATED` means that semantic/numerical evaluation is outside the
  operation's contract; it is not a native-runtime failure.

## Acceptance

The implementation is complete only when focused runtime and distribution
tests pass, a multi-frame numerical fixture is deterministic across three
runs, generated artifacts validate, golden tests pass, and `reason ci --json`
passes.

Validation completed on 2026-07-23 with `reason ci --json`: 1085 tests passed,
artifact and Golden validation passed, and the canonical agent report records
`VALIDATED`.
