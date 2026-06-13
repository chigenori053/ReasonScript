# ReasonScript

ReasonScript is a reasoning-first language for proofable AI workflows,
deterministic execution, and rollback-safe systems.

# Platform v0.1 Alpha

The current platform release is `0.1.0-alpha` (2026-06-13). It integrates:

```text
ReasonScript Source
  -> parser/0.1
  -> reasonscript-ast/0.1
  -> compiler/0.1
  -> reason-ir/0.1
  -> common-dto/0.1
  -> Runtime
  -> InferenceResult
```

Release documentation:

- `docs/ReasonScript_Platform_v0.1_Alpha_Release_Specification.md`
- `docs/ReasonScript_Platform_v0.1_Alpha_Release_Report.md`
- `release/v0.1-alpha/manifest.json`
- `CHANGELOG.md`

Run the integrated release gate with:

```sh
python3 release/v0.1-alpha/run_release_validation.py
```

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

The Phase 3 conformance framework is under `conformance/`. Run every layer and
refresh the certification report with:

```sh
python3 conformance/run_conformance.py
```
