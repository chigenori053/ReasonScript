# ReasonScript Executable Check Contract Phase 0 Report

## Completion Summary

Phase 0 is complete. Default `reason check` now validates executable
Computation IR support in addition to Surface syntax and semantics, and
`--surface-only` explicitly preserves the former non-executable validation
mode.

## Implemented Features

- One shared optimized Computation IR lowering and validation function for
  `reason check` and `reason build`.
- Package, workspace, and standalone-file executable checks.
- Stable `IR-LOWER-*` failures at check time with `computation_ir` stage
  metadata in standalone JSON output.
- Explicit `check_mode` and `execution_checked` result fields.
- `--surface-only` CLI mode and help text.
- Executable versus Surface-only classification for the v0.5 examples corpus.

## Validation Results

- Focused Phase 0 and affected CLI/package regressions: 17 passed.
- Official examples: 10/10 valid expectations and 6/6 invalid expectations
  passed; 6 are executable and 4 are explicitly Surface-only.
- Canonical `reason ci --json`: PASS.
- Repository tests: 1228 passed.
- Workspace, diagnostics, artifact, golden, agent-protocol, and compatibility
  phases: PASS.

## Generated Artifacts

- `agent_report.json` records task `Executable Check Contract Phase 0`, status
  `VALIDATED`, 1228 passing tests, and generated artifacts.
- Existing canonical artifact and golden manifests validated without updates.

## Compatibility Notes

- Existing Surface validation remains available through `--surface-only`.
- Default `reason check` is intentionally stricter: a source that cannot be
  lowered for the production Rust host now fails before build.
- Canonical lowering diagnostic codes are unchanged.
- Build artifacts and Computation IR schema remain unchanged.

## Remaining Work

- Runtime I/O examples remain Surface-only until runtime input/print lowering
  is added.
- Struct-pattern and Optional-match examples remain Surface-only until Phase 1
  adds enum, Optional, and match execution support.
- `reason test` still validates compilation rather than executing language
  assertions; that is scheduled for a later phase.

Phase 1 update: the struct-pattern and Optional-match item above is complete;
only the two runtime-I/O examples remain Surface-only.
