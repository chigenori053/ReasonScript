# Versioning Strategy Report

Classification: Requires Refactoring

Scope: Language, Runtime, Execution Architecture, SDK, World Model SDK, LSP, and
IDE.

## Findings

- VR-001: Version numbers are not aligned. Existing layers use independent
  versions such as `reason-ir/0.1`, `world-model-sdk/0.4`,
  `reasonscript-lsp/0.1`, and `reasonscript-ide/0.1`.
- VR-002: Compatibility guarantees are local to each specification and need a
  platform-level compatibility matrix.
- VR-003: Beta versioning can begin after Platform Architecture v1.0 freezes
  layer ownership, trace policy, diagnostic policy, and package resolution.

## Strategy

- Keep layer schema versions independent.
- Introduce a platform release label, starting with
  `ReasonScript Platform Architecture v1.0`.
- Add a compatibility matrix mapping platform releases to layer versions.
- Require every emitted DTO, report, LSP payload, IDE result, and toolchain
  structured output to include schema metadata when machine-readable.

## Beta Gate

Beta starts only after package graph, ReasoningTrace, platform diagnostics, and
ExecutionScope are specified.
