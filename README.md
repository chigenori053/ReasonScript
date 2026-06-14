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
- `docs/ReasonScript_Language_Specification_v0.1.md`
- `docs/ReasonScript_Language_Phase_1_Validation_Report.md`
- `docs/ReasonScript_Operational_Semantics_v0.1.md`
- `Operational_Semantics_Validation_Report.md`
- `release/v0.1-alpha/manifest.json`
- `CHANGELOG.md`

Run the integrated release gate with:

```sh
python3 release/v0.1-alpha/run_release_validation.py
```

# Language Surface v0.1

ReasonScript Language Surface v0.1 was released on 2026-06-14. It fixes the
deterministic path:

```text
ReasonScript Source
  -> Surface AST
  -> Semantic AST
  -> Reason IR
  -> ExecutionPlan
```

Run its release gate with:

```sh
python3 release/language-surface-v0.1/run_release_validation.py
```

The normative release specification is
`docs/ReasonScript_Language_Surface_v0.1_Release_Specification.md`.

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

Validate the Language v0.1 core model and module system with:

```sh
python3 -m unittest discover \
  -s language_spec_validation_tests -p 'test_*.py' -v
```

Validate Operational Semantics v0.1 and the Runtime contract with:

```sh
python3 -m unittest discover \
  -s operational_semantics_tests -p 'test_*.py' -v
python3 -m unittest discover \
  -s runtime_semantics_validation_tests -p 'test_*.py' -v
cargo test --manifest-path HybridRuntime/Cargo.toml \
  --test operational_semantics_validation
```
