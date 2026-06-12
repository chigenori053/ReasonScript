# ReasonScript

ReasonScript is a reasoning-first language for proofable AI workflows,
deterministic execution, and rollback-safe systems.

# Reason IR schema and validator

The versioned Reason IR 0.1 contract is defined in
`schemas/reason_ir.schema.json`. Validate one or more documents with:

```sh
cargo run --manifest-path HybridRuntime/Cargo.toml \
  --bin reason-ir-validator -- fixtures/valid/dog_to_animal.json
```

Conformance fixtures are stored under `fixtures/valid` and
`fixtures/invalid`.

Common DTO bindings for Rust, Python, TypeScript, Go, and Java are stored under
`dto/`. The normative DTO contract is
`docs/Common_DTO_Specification_v0.1.md`.
