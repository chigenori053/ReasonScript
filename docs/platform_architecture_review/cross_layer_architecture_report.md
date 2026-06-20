# Cross-Layer Architecture Report

Classification: Requires Refactoring

Scope:

- Language to Runtime
- Runtime to SDK
- SDK to World Model SDK
- Execution Architecture to Runtime
- LSP to Compiler
- IDE to Toolchain

## Findings

- CL-001: Responsibilities are duplicated around diagnostics, traces, source
  indexing, and execution result assembly.
- CL-002: Hard architectural cycles are not present in the main user-facing
  paths. Risk exists when SDK convenience imports re-export runtime integration
  details.
- CL-003: Trace systems are duplicated across coordinator, simulation,
  reconstruction, runtime, transaction, and operational semantics tests.
- CL-004: Serialization formats are coherent at the fixture level but not yet
  governed by a single version policy.
- CL-005: Versioning rules are documented per layer but not aligned under a
  Beta compatibility contract.

## Integration Risks

- LSP source index diverges from compiler semantics.
- IDE diagnostics diverge from LSP diagnostics.
- Runtime trace payloads cannot be combined without lossy adapters.
- Toolchain package resolution becomes incompatible with language imports.

## Recommendations

- Add canonical platform diagnostic and trace DTOs.
- Establish a package graph service owned by Toolchain.
- Require every layer to declare schema/version metadata.
