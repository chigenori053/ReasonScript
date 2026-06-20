# ReasonScript Roadmap

## Phase 1
- core semantics
- grammar draft
- parser skeleton
- runtime prototype

## Phase 2
- DBM adapter
- REPL
- proof engine
- deterministic apply runtime

## Phase 3
- OSS ecosystem
- VS Code syntax
- package registry

## Post-Alpha 1.0

Primary track:

- World Model SDK Phase 1 specification
- World Model SDK Phase 1 implementation
- World Model SDK Phase 2 spatial and geometry layer
- World Model SDK Phase 3 semantic reconstruction layer

Parallel track:

- LSP Phase 1 specification
- LSP Phase 1 minimal implementation
- IDE Integration Phase 1
- Platform Architecture Review Phase 1

Completed in this milestone:

- `docs/World_SDK_Phase_1_Specification.md`
- `docs/LSP_Phase_1_Specification.md`
- `sdk.world`
- `world_sdk_phase1_tests`
- `frontend.lsp`
- `lsp_phase1_tests`
- `frontend.ide`
- `ide_phase1_tests`
- `docs/platform_architecture_review/`
- `platform_architecture_review_tests`

## Beta Planning

Architecture baseline:

- `docs/platform_architecture_review/platform_architecture_v1.md`

P0 gates:

- Specify `reasoning-trace/0.1`
- Specify platform diagnostic DTO
- Specify Toolchain package graph and lockfile
- Specify ExecutionScope and complete CallStack runtime model

P1 stabilization:

- Refactor LSP symbol index to compiler source spans
- Add structured JSON output to all `reason` commands
- Add runtime registry capability metadata
- Add SDK public API manifest

P2 ecosystem:

- Add editor adapters over the editor-agnostic IDE core
- Add read-only ReasonGraph, ExecutionPlan, World, and trace viewers
- Begin package registry design
