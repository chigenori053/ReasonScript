# ReasonScript

ReasonScript is a reasoning-first language for proofable AI workflows,
deterministic execution, and rollback-safe systems. It compiles source
through a deterministic pipeline — Surface AST, Semantic AST, Reason IR,
and ExecutionPlan — into a validated, reproducible runtime result.

Current release: **v0.5.2**. See [`CHANGELOG.md`](CHANGELOG.md) for the
detailed history and [`docs/roadmap.md`](docs/roadmap.md) for what's next.

## What it does

- **Deterministic execution** — every run produces a reproducible,
  validated `ExecutionPlan` and `InferenceResult`.
- **Reasoning artifacts** — `ReasoningModel`, `ReasoningEvaluationReport`,
  and `ReasoningRuntimeResult` give an inspectable, versioned record of how
  a result was reached.
- **ReasonUnit Objects** — a canonical, portable object format (`RUO`) with
  a native runtime type, CLI integration, and a migration path from legacy
  formats.
- **Cross-language DTO bindings** — Rust, Python, TypeScript, Go, and Java
  bindings share one normative contract (`docs/specifications/Common_DTO_Specification_v0.1.md`).
- **Tooling** — a CLI (`reason`), an IDE (`apps/reasonscript-ide`), a VS
  Code extension (`vscode-extension/`), and a browser playground
  (`playground/`).

## Installation

Platform-specific installers and requirements:

- [Linux](docs/installation/linux.md)
- [macOS](docs/installation/macos.md)
- [Windows](docs/installation/windows.md)
- [Uninstall](docs/installation/uninstall.md) /
  [Troubleshooting](docs/installation/troubleshooting.md)

For local development from source:

```sh
git clone git@github.com:chigenori053/ReasonScript.git
cd ReasonScript
pip install -e .
```

## Quickstart

```sh
./reason ci --json
./reason reasoning-runtime run examples/v0_8/reasoning_runtime/animal_isa.rsn --json
```

The full walkthrough, including generating and validating `ReasoningModel`
and `ReasoningEvaluationReport` artifacts, is in the
[v0.5 Quickstart guide](docs/guides/ReasonScript_v0_5_Quickstart.md). CLI
usage is documented in the
[CLI Reference](docs/reference/ReasonScript_v0_5_CLI_Reference.md).

## Documentation

[`docs/README.md`](docs/README.md) is the full documentation index —
language specifications, platform contracts, development guides, and
release reports. Highlights:

- [Language Specification v0.1](docs/specifications/ReasonScript_Language_Specification_v0.1.md)
- [Semantic Language Core v0.2](docs/specifications/ReasonScript_Semantic_Language_Core_v0.2.md)
  (frozen 2026-06-15)
- [Operational Semantics v0.1](docs/specifications/ReasonScript_Operational_Semantics_v0.1.md)
- [Reason IR schema](schemas/reason_ir.schema.json), validated with:

  ```sh
  cargo run --manifest-path HybridRuntime/Cargo.toml \
    --bin reason-ir-validator -- fixtures/valid/dog_to_animal.json
  ```

## Conformance

The conformance framework under `conformance/` runs every validation layer
and refreshes the certification report:

```sh
python3 conformance/run_conformance.py
```

## Contributing

Issues and pull requests are welcome. There is no formal contribution
guide yet — for anything beyond a small fix, please open an issue first to
discuss the change.

## License

A repository-wide `LICENSE` has not been finalized yet. The
`vscode-extension/` package is MIT-licensed; treat the rest of the
repository as all-rights-reserved until a root `LICENSE` file is added.
