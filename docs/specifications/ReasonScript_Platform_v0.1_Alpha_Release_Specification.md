# ReasonScript Platform v0.1 Alpha Release Specification

Version: `0.1.0-alpha`
Release status: Released
Release date: 2026-06-13
Platform type: Reasoning Language Platform

## Release Declaration

ReasonScript Platform v0.1 Alpha is the first integrated platform release
covering the Runtime foundation, versioned platform ABI, common DTO boundary,
language frontend, and conformance framework.

## Architecture

```text
ReasonScript Source
          |
      parser/0.1
          |
 reasonscript-ast/0.1
          |
     compiler/0.1
          |
     reason-ir/0.1
          |
   common-dto/0.1
          |
 Execution Coordinator
          |
 Transaction Kernel
          |
     State Kernel
          |
   InferenceResult
```

## Runtime Foundation

Status: Stable for the fixed v0.1 Alpha interfaces.

Components:

- ReasonUnit
- Runtime API
- Execution Model
- Reason IR
- Transaction Model

The execution architecture is a state-first layered Hybrid Runtime. Optional
graph planning, constraint evaluation, and memory/effect adapters feed the
state transition kernel. Only the State Kernel may change committed state.

The transaction protocol is:

```text
Prepare -> Validate -> Commit -> StateDelta
```

Commit is the only forward state mutation. Rollback is represented by a traced
reverse delta. Execution plans are immutable.

## Platform Foundation

### Reason IR

- ABI: `reason-ir/0.1`
- Serialization: UTF-8 JSON
- Documents: `ReasonIR`, `ExecutionPlan`, `StateDelta`, `InferenceResult`,
  `Trace`, and `TransactionRecord`

### Common DTO

DTO declarations are supplied for Rust, Python, TypeScript, Go, and Java.
They share the Reason IR JSON field names.

### Frontend

- AST ABI: `reasonscript-ast/0.1`
- Parser contract: `parser/0.1`
- Compiler contract: `compiler/0.1`
- AST root: `ModuleNode`
- Core nodes: Goal, State, Transition, Constraint, Context, and Metadata

The parser supports the Phase 2 minimal statements `goal`, `state`,
`transition`, `constraint`, `context`, and `import`.

The compiler performs AST validation, default expansion, policy injection,
and deterministic Reason IR lowering. Runtime execution is outside the
compiler package.

## Validation Baseline

- HybridRuntime: 121 tests passed
- AST validation: 12 tests passed
- Platform conformance: Layers 0-4 passed
- AST ABI conformance: Layers 0-4 passed
- Parser conformance: Layers 0-4 passed
- Compiler conformance: Layers 0-5 passed
- Source -> Parser -> AST -> Compiler -> Reason IR -> Runtime: passed

The machine-readable release manifest and gate results are stored under
`release/v0.1-alpha/`.

## Fixed Interfaces

The following identifiers are fixed for v0.1 Alpha:

- `reason-ir/0.1`
- `reasonscript-ast/0.1`
- `parser/0.1`
- `compiler/0.1`
- `transaction/0.1`
- `common-dto/0.1`
- `conformance-framework/0.1`

Breaking changes require a new explicit interface version. Additive changes
must continue to pass the v0.1 Alpha release gate.

## Supported Binding Status

| Binding | Declaration | Executable evidence |
|---|---|---|
| Rust | Available | DTO and cross-language tests passed |
| Python | Available | DTO and cross-language tests passed |
| TypeScript | Available | Type-check and cross-language tests passed |
| Go | Available | Not executed: Go toolchain unavailable |
| Java | Available | Records compile; JSON codec adapter unavailable |

This release does not claim Full Compatible certification across all five
languages.

## Known Limitations

- Syntax evolution and formatting rules remain experimental.
- Macro system, language server, formatter, and optimizer are not implemented.
- Distributed Runtime, persistence, and event sourcing are not implemented.
- Go executable conformance and Java JSON codec conformance remain incomplete.
- RuntimeReal emits non-fatal compiler warnings in its supplemental suite.

## Roadmap

1. Language Frontend Foundation Phase 4: Syntax Validation
2. SDK expansion for Python, TypeScript, Go, and Java
3. DBM, WorldModel Simulator, and MemorySpace integration
4. ReasonScript Platform v1.0

## Release Statement

The v0.1 Alpha release demonstrates the complete:

```text
Source -> AST -> Reason IR -> Runtime
```

pipeline and moves ReasonScript from isolated foundation validation into an
integrated Reasoning Language Platform development phase.
