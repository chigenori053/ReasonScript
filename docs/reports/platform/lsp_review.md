# LSP Review Report

Classification: Partially Complete

Scope: diagnostics, hover, completion, definition, references, and symbol index.

## Findings

- LSP-001: Semantic information is partially duplicated. LSP Phase 1 reuses the
  parser for diagnostics but keeps a lightweight source index for locations
  because the current AST does not carry source ranges.
- LSP-002: Phase 2 refactoring can be added safely if source ranges become part
  of parser output and the LSP index becomes a projection of compiler metadata.
- LSP-003: Debugging can integrate later through ExecutionCoordinator and
  ReasoningTrace; it should not be added to the LSP core as runtime logic.

## Architectural Gaps

- Canonical source-span metadata in AST/compiler output.
- Structured diagnostic conversion from compiler/toolchain/runtime to LSP.
- Workspace-level incremental import graph.

## Recommendations

- Add source ranges to AST nodes or compiler side tables.
- Keep LSP transport independent from analysis core.
- Route future debug data through DAP/IDE using ExecutionCoordinator traces.
