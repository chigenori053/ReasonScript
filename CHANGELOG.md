# Changelog

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
