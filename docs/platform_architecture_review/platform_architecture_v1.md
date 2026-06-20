# ReasonScript Platform Architecture v1.0

Status: Architecture Baseline Complete

Schema: `reasonscript-platform-review/1.0`

## Architecture Classification

| Subsystem | Classification | Rationale |
| --- | --- | --- |
| Language | Partially Complete | Rich Alpha surface exists; function execution and package dependency semantics remain incomplete. |
| Runtime | Partially Complete | RuntimeReal and HybridRuntime are available through registries; diagnostics, capabilities, and trace contracts need consolidation. |
| Execution Architecture | Partially Complete | ExecutionCoordinator exists; ExecutionScope and full function CallStack semantics remain missing. |
| Toolchain | Partially Complete | Standard commands exist; multi-package dependency resolution and registry are missing. |
| SDK | Partially Complete | Builders and validators exist; public API/version policy needs freeze. |
| World Model SDK | Partially Complete | Core, spatial, semantic, and simulation layers exist; trace and agent/planning boundaries need formalization. |
| LSP | Partially Complete | Phase 1 capabilities exist; source-span and semantic-index duplication require refactoring. |
| IDE | Partially Complete | Editor-agnostic command integration exists; editor adapters and structured toolchain output remain missing. |
| Cross-Layer Architecture | Requires Refactoring | Trace, diagnostic, versioning, and package boundaries are not yet platform-wide contracts. |
| ReasoningTrace | Missing | Proposal exists; schema and adapters are not implemented. |
| Versioning | Requires Refactoring | Layer versions exist but need a platform compatibility matrix. |

## Risk Assessment

| Risk | Severity | Mitigation |
| --- | --- | --- |
| Trace fragmentation | High | Define `reasoning-trace/0.1` and adapters before debugger/visualization work. |
| Diagnostic divergence | High | Define a platform diagnostic DTO and conversion rules for compiler, runtime, LSP, IDE, and toolchain. |
| Package graph ambiguity | High | Make Toolchain own package graph, dependency resolution, and lockfiles. |
| LSP semantic duplication | Medium | Add source spans to compiler/parser output and derive LSP symbols from compiler metadata. |
| Runtime capability drift | Medium | Add runtime registry capability/version metadata. |
| Editor adapter divergence | Medium | Keep IDE core editor-agnostic and make editor extensions thin wrappers. |

## Beta Readiness Assessment

Current state: Not Beta-ready.

Alpha 1.0 is architecturally coherent enough to freeze as a baseline, but Beta
requires four platform contracts:

- Platform diagnostics
- ReasoningTrace
- Toolchain package graph
- ExecutionScope and CallStack semantics

## Post-Alpha Roadmap

P0:

- Specify `reasoning-trace/0.1`.
- Specify platform diagnostic DTO.
- Specify Toolchain package graph and lockfile.
- Specify ExecutionScope and complete CallStack runtime model.

P1:

- Refactor LSP symbol index to compiler source spans.
- Add structured JSON output to all `reason` commands.
- Add runtime capability metadata.
- Add SDK public API manifest.

P2:

- Add editor adapters for VS Code-compatible clients and Neovim.
- Add read-only ReasonGraph, ExecutionPlan, World, and trace viewers.
- Begin package registry design.

## Freeze Statement

ReasonScript Platform Architecture v1.0 is the architectural freeze point
between ReasonScript Platform Alpha 1.0 and ReasonScript Platform Beta Planning.
