# Python Reference Runtime Policy

## Status

As of Rust Runtime Consolidation Phase 7, Python execution engines are
reference-only. Product execution uses `reason-runtime-host`; a missing host,
unsupported lowering, capability denial, bridge failure, or native runtime
error is returned as a structured diagnostic without executing Python.

## Allowed use

The Python AST evaluator, Computation IR interpreter, Tensor runtime, RUO
runtime, Vision runtime, and reasoning references may be imported by
differential tests, benchmark scripts, and explicit development validation.
They must not be imported by standalone execution, project execution, project
validation, Tensor artifact commands, or manifest generation.

## Deletion gate

Reference implementations remain until their differential oracle value is
replaced by native golden vectors or an independent specification harness.
Phase 9 may delete a reference only when no retained test or benchmark imports
it and the runtime-consolidation deletion gates remain green.
