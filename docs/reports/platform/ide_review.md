# IDE Review Report

Classification: Partially Complete

Scope: workspace detection, build, run, test, check, diagnostics, and output
channels.

## Findings

- IDE-001: Toolchain integration is sufficient for Phase 1. IDE commands invoke
  only `reason build`, `reason run`, `reason test`, and `reason check`.
- IDE-002: Debugger integration can be added later if it consumes
  ExecutionCoordinator results and ReasoningTrace, without bypassing Toolchain.
- IDE-003: Visualization can be added later as a read-only projection of
  ReasonGraph, ExecutionPlan, World, and trace artifacts.

## Architectural Gaps

- Editor-specific extension packaging is not implemented.
- Toolchain commands do not all expose structured machine-readable output.
- Unified Problems panel integration depends on diagnostic normalization.

## Recommendations

- Keep the core IDE API editor-agnostic.
- Add VS Code and Neovim adapters as thin wrappers over `frontend.ide`.
- Do not add runtime inspection until ExecutionCoordinator trace contracts are
  frozen.
