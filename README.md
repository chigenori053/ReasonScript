# ReasonScript

ReasonScript is a reasoning-first language and runtime for deterministic,
inspectable AI workflows. It compiles `.rsn` programs through a Surface AST,
Semantic AST, Reason IR, and ExecutionPlan, then executes them with the native
ReasonRuntime host.

## Release status

The current release is **v0.5.5.9**.

- Language version: `0.7`
- Runtime compatibility: `>=0.5.0,<0.6.0`
- Source-install requirement: Python 3.11 or later, Git, and Rust/Cargo
- Supported targets: macOS arm64/x86_64, Windows x86_64, and Linux x86_64

The release definition is available in
[v0.5.5.9 Release Definition](docs/specifications/ReasonScript_v0_5_5_9_Release_Definition.md).
For changes, see the [changelog](CHANGELOG.md). The macOS arm64 update
procedure is documented in the
[v0.5.5.9 installation guide](docs/installation/ReasonScript_v0_5_5_9_Installation.md).

## Highlights

- **Native deterministic runtime** — production calculations execute through
  the Rust runtime host, with structured diagnostics and reproducible results.
- **Language and standard library** — modules, typed calculations, enums,
  `Optional`, pattern matching, strings, collections, bounded recursion, and
  execution-based assertions.
- **Tensor and optimization** — native Tensor operations, autograd,
  `optimizer.*` functions, and deterministic numeric semantics.
- **Reasoning and objects** — reasoning operations, ReasonUnit Objects (RUO),
  ReasonGraph bindings, Vision integration, and cluster execution.
- **Tooling** — the `reason` CLI, language server, CodeViewer, VS Code
  extension, browser playground, schemas, artifacts, and conformance suites.

## Install from source

Clone the repository and run the user-scoped installer:

```sh
git clone https://github.com/chigenori053/ReasonScript.git
cd ReasonScript
./scripts/install.sh --non-interactive
```

Add `~/.reasonscript/bin` to your `PATH` if the installer reports that it is
missing, then verify the installation:

```sh
reason --version
reason doctor --json
reason install-validate --json
```

Platform notes are available for [macOS](docs/installation/macos.md),
[Windows](docs/installation/windows.md), and
[Linux](docs/installation/linux.md). For local package updates, use the
[v0.5.5.9 installation guide](docs/installation/ReasonScript_v0_5_5_9_Installation.md).

## Quick start

Run validation from a source checkout:

```sh
./reason version-validate --json
./reason check examples/v0_8/reasoning_runtime/animal_isa.rsn --json
./reason reasoning-runtime run examples/v0_8/reasoning_runtime/animal_isa.rsn --json
```

The canonical repository validation command is:

```sh
./reason ci --json
```

For the full command surface, run `reason help`.

## Documentation

The [documentation index](docs/README.md) covers language specifications,
runtime and platform contracts, development guides, and reports. Key references:

- [Language Specification v0.1](docs/specifications/ReasonScript_Language_Specification_v0.1.md)
- [Semantic Language Core v0.2](docs/specifications/ReasonScript_Semantic_Language_Core_v0.2.md)
- [Operational Semantics v0.1](docs/specifications/ReasonScript_Operational_Semantics_v0.1.md)
- [Reason IR schema](schemas/reason_ir.schema.json)
- [Runtime consolidation plan](docs/development/runtime_rust_consolidation_plan.md)

## Contributing

Issues and pull requests are welcome. For changes larger than a small fix,
please open an issue first so the scope and compatibility impact can be
discussed. Run `./reason ci --json` before submitting a change.

## License

ReasonScript is licensed under the [Apache License 2.0](LICENSE).
The `vscode-extension/` package is separately MIT-licensed; see
[its license](vscode-extension/LICENSE). Third-party dependencies retain their
own licenses.
