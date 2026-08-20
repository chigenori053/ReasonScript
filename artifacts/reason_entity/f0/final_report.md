# ReasonScript Reason Entity Foundation — Phase F0 Baseline Report

## Completion Summary

The v0.5.4.6 observable behavior of the compiler pipeline and integrated runtime is frozen as a deterministic baseline for RS-RE-FSM-001.

## Implemented Features

- Surface AST / Semantic AST / Reason IR / ExecutionPlan digests for the example fixture corpus.
- Diagnostic code inventory and one invalid-fixture regression probe.
- Self-contained Tensor numeric baseline (no filesystem dependency).
- Wall-clock performance baseline for later Phase comparison.

## Validation Results

- Fixtures compiled: 14.
- Determinism: PENDING_VERIFICATION.

## Generated Artifacts

All canonical JSON documents are recorded by `run_manifest.json` with SHA-256 digests and byte sizes.

## Compatibility Notes

No lexer, parser, compiler, runtime, or diagnostic behavior is modified by this Phase.

## Remaining Work

Proceed to Phase F1 (Type Foundation Repair) only after this baseline is verified byte-identical across three independent generations.
