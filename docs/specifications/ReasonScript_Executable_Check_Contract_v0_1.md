# ReasonScript Executable Check Contract v0.1

Status: Accepted for Phase 0 implementation

## 1. Objective

`reason check` is the product-facing preflight for Rust-host execution. A
successful default check therefore guarantees that the validated closed
package can be lowered to valid `reason-computation-ir/0.1` by the same
pipeline used by `reason build`.

This contract removes the former state in which Surface validation succeeded
but `reason build` later failed with `IR-LOWER-*`.

## 2. Check modes

The default mode is `executable`:

```text
reason check
reason check source.rsn
```

It performs, in order:

1. parsing and namespace resolution;
2. Surface semantic validation;
3. Computation IR lowering and optimization; and
4. Computation IR structural validation.

The compatibility mode is explicit:

```text
reason check --surface-only
reason check source.rsn --surface-only
```

It performs only steps 1 and 2. Success in this mode does not claim that the
source can be built or executed.

## 3. Diagnostics

Unsupported executable constructs retain their canonical lowering diagnostic,
including `IR-LOWER-005` for an unsupported statement and `IR-LOWER-006` for
an unsupported expression. Standalone JSON output identifies the stage as
`computation_ir` and reports `check_mode` and `execution_checked`.

No generated build artifact is written by either check mode.

## 4. Build parity

`reason check` and `reason build` shall call one shared executable-lowering
function. The shared function includes IR optimization and validation so that
the two commands cannot silently drift.

For an unchanged package and toolchain version:

```text
default check succeeds => build does not fail with IR-LOWER-*
```

Filesystem publication, stale output cleanup, runtime-host discovery, and
runtime execution are outside the check guarantee.

## 5. Example classification

Examples accepted by the default examples suite are executable examples.
Examples that intentionally demonstrate a valid Surface feature not yet
implemented in Computation IR must be explicitly classified as `surface_only`.

Phase 1 narrows the `surface_only` set to:

- `006_runtime_input_print.rsn`
- `007_runtime_operation.rsn`

These return to the executable set when runtime I/O is represented in
Computation IR and the Rust host. `008_struct_pattern.rsn` and
`009_optional_match.rsn` are executable as of Phase 1.

## 6. Acceptance tests

- Default package check accepts Surface-valid executable `match` and
  `some(...)` programs.
- `--surface-only` remains available for syntax/semantic-only inspection.
- Default standalone check emits the canonical lowering failure as a
  `computation_ir` diagnostic in JSON.
- An executable package accepted by check builds successfully through the
  shared lowering function.
- The examples report distinguishes executable and Surface-only cases.
