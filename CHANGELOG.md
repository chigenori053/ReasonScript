# Changelog

## ReasonScript Language Layer v0.6-D - 2026-06-29

### Added

- Added Human Surface top-level construct policy.
- Defined `model` as active preferred syntax.
- Defined `module` as active compatibility syntax.
- Reserved `world` for WorldModel / simulation-domain syntax.
- Reserved `system` for multi-model orchestration syntax.
- Reserved `component` for UI / SDK structural composition syntax.
- Added reserved top-level construct diagnostic policy.

### Fixed

- Clarified that reserved top-level constructs must not silently parse as `model` or `module`.
- Clarified that `source_kind` remains L1/L7 metadata unless a future specification defines distinct core semantics.
- Preserved module/model L3-L6 equivalence guarantees from v0.6-B.

### Validation

- model active preferred syntax policy verified.
- module active compatibility syntax policy verified.
- reserved construct diagnostics verified.
- module/model core non-regression verified.
- top-level construct projection policy verified.
- Playground frontend build verified.

## ReasonScript Language Layer v0.6-C - 2026-06-29

### Added

- Added L7 Developer Projection support for `source_kind`.
- Added Playground Summary View presentation for `model` and `module`.
- Displayed `model` as preferred Human Surface syntax.
- Displayed `module` as compatibility syntax.
- Displayed normalized ReasonGraph target for top-level constructs.
- Added Diagnostics View support for `diagnostics.json`.

### Fixed

- Clarified that source spelling differences are projection metadata, not Reason IR semantics.
- Prevented Developer Projection from implying different core semantics for `module` and `model`.

### Validation

- Source kind projection verified.
- model preferred syntax projection verified.
- module compatibility syntax projection verified.
- Diagnostics artifact consumption verified.
- L3-L6 non-regression verified.
- Playground frontend build verified.

## ReasonScript Language Layer v0.6-B - 2026-06-28

### Added

- Accepted `model Example { ... }` as a top-level Human Surface alias.
- Added `source_kind` to Surface AST to preserve original top-level spelling.
- Added module/model equivalence validation across Reason IR, ExecutionPlan,
  Simulation, and Knowledge.
- Added `diagnostics.json` to Playground pipeline artifact export.

### Fixed

- Clarified that Human Surface spelling must not affect Reason IR semantics.
- Strengthened CI/CD coverage for Language Layer artifact consistency.

### Validation

- Surface AST source_kind distinction verified.
- Reason IR equivalence verified.
- ExecutionPlan equivalence verified.
- Simulation and Knowledge equivalence verified.
- Playground artifact contract verified.

## reasonscript-language-surface/0.5 - 2026-06-28

ReasonScript Language Surface v0.5 feature freeze.

### Frozen Surface

- Module system, declarations, type system, expressions, and statements
- Literal, enum, optional, struct, nested struct, guard, OR, and range patterns
- Source -> Surface AST -> Semantic AST -> Reason IR -> ExecutionPlan ->
  Simulation -> Knowledge pipeline
- Pattern Identity, canonical path generation, and branch evidence propagation

### Fixed Interfaces

- `reasonscript-language-surface/0.5`
- `parser/0.5`
- `reasonscript-ast/0.5`
- `reason-ir/0.5`
- `execution-plan/0.5`

### Compatibility Policy

- `0.5.x` releases may include bug fixes, diagnostics, compiler optimizations,
  and performance improvements.
- Syntax, semantic meaning, IR schema, canonical path generation, and Pattern
  Identity are frozen for the v0.5 line.
- New language features are deferred to v0.6.

## reasonscript-semantic-language/0.2 - 2026-06-15

ReasonScript Semantic Language v0.2 Core freeze.

### Frozen Core

- SemanticUnit and the seven adopted SemanticUnit types
- SemanticRelation and the eight core relation types
- SCV-1 structural validation
- Reasoning Space and SemanticPlan
- deterministic SemanticSimulation and SimulationResult
- validated Knowledge emergence with complete evidence

### Guarantees

- deterministic reasoning for identical graph, plan, and constraints
- SCV-1 enforcement throughout the reasoning pipeline
- immutable Reasoning Space during simulation
- trace, evidence, and confidence preservation
- reproducible SimulationResult and Knowledge JSON

### Out of Scope

- SCV-2 through SCV-5
- Knowledge repositories, persistence, retrieval, and re-reasoning
- MemorySpace, WorldModel, natural language parsing, and external execution

## reasonscript-language-surface/0.1 - 2026-06-14

ReasonScript Language Surface v0.1 release.

### Released

- Deterministic Source -> Surface AST -> Semantic AST -> Reason IR ->
  ExecutionPlan pipeline
- Module namespaces, imports, aliases, visibility, and qualified names
- Declarations, relations, expressions, patterns, statements, and Calculations
- Primitive and Reason State type annotations as validation contracts
- Canonical `node_type` serialization and round-trip compatibility
- Fixed AST, expression, pattern, statement, Calculation, type, and namespace
  validation families

### Fixed Interfaces

- `reasonscript-language-surface/0.1`
- `reasonscript-ast/0.1`
- `parser/0.1`
- `compiler/0.1`
- `reason-ir/0.1`
- `execution-plan/0.1`
- `reasonscript-calculation-semantics/0.1`

## 0.1.0-alpha - 2026-06-13

First integrated ReasonScript Platform alpha release.

### Added

- State-first layered Hybrid Runtime and transaction model
- Versioned `reason-ir/0.1` JSON ABI
- Common DTO declarations for Rust, Python, TypeScript, Go, and Java
- Five-layer platform conformance framework
- Versioned `reasonscript-ast/0.1` semantic AST ABI
- Deterministic `parser/0.1` Source-to-AST contract
- Deterministic `compiler/0.1` AST-to-Reason-IR contract
- End-to-end Source -> AST -> Reason IR -> Runtime validation

### Fixed Interfaces

- `reason-ir/0.1`
- `reasonscript-ast/0.1`
- `parser/0.1`
- `compiler/0.1`
- `transaction/0.1`
- `common-dto/0.1`
- `conformance-framework/0.1`

### Known Limitations

- The user-facing syntax remains experimental.
- Macros, language server, formatter, optimizer, distributed Runtime,
  persistence, and event sourcing are not included.
- Go conformance was not executed in the release environment because the Go
  toolchain was unavailable.
- Java DTO declarations compile, but a Java JSON codec adapter is not included.
- Full five-language SDK compatibility certification is not granted.
