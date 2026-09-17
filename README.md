# ReasonScript

ReasonScript is a reasoning-first programming language and native runtime for
deterministic, inspectable AI workflows. A `.rsn` source file is parsed and
validated, lowered through semantic and computation IR, and executed by the
Rust runtime host.

> **Note on Language Identity**: ReasonScript is an independent programming language. It is **not affiliated with, derived from, or compatible with ReScript, Reason, or ReasonML**. ReasonScript programs use `.rsn` source files, the canonical `reason` CLI tool, and native syntax constructs (`model`, `module`, `fn`, `calculation`, `goal`, `state`).

Current release: **v0.5.5.13** (language core `0.7`).

## Install

The prebuilt V0.5.5.13 package supports macOS arm64. Download the ZIP and its
SHA-256 sidecar from the [V0.5.5.13 GitHub Release](https://github.com/chigenori053/ReasonScript/releases/tag/v0.5.5.13), verify it, and install or update it with:

```sh
shasum -a 256 -c reasonscript-0.5.5.13-macos-arm64.zip.sha256
reason update --package reasonscript-0.5.5.13-macos-arm64.zip
```

Source installation requires Python 3.11+, Git, and Rust/Cargo.

```sh
git clone https://github.com/chigenori053/ReasonScript.git
cd ReasonScript
./scripts/install.sh --non-interactive
```

Add `~/.reasonscript/bin` to `PATH` if requested, then verify the install:

```sh
reason --version
reason doctor --json
reason install-validate --json
```

See the [installation guide](docs/installation/README.md) for the platform
support matrix, source installation, updates, troubleshooting, and removal.

## Try the language

```reasonscript
model Hello {
  fn Message() -> string {
    return "Hello, World!"
  }

  calculation Greeting {
    result = Message()
  }
}
```

Save this as `hello.rsn`, then check and run:

```sh
reason check hello.rsn
reason run hello.rsn --json
```

The output will confirm successful execution and display the calculated result:
```json
{
  "runtime_result": {
    "calculations": {
      "Greeting": "Hello, World!"
    },
    "result": "Hello, World!",
    "status": "success"
  }
}
```

To create and run a project workspace instead:

```sh
reason init my-project
cd my-project
reason check
reason build
reason run --json
```

## Documentation

- [Documentation index](docs/README.md)
- [Quickstart](docs/guides/quickstart.md)
- [Language reference](docs/language-reference.md) — the human-readable
  source-language contract
- [Standard library](docs/standard-library.md)
- [CLI reference](docs/reference/cli.md)
- [ReasonUnit Objects](docs/reasonunit-object.md)
- [Contributing](CONTRIBUTING.md)
- [Security policy](SECURITY.md)
- [Code of conduct](CODE_OF_CONDUCT.md)
- [Changelog](CHANGELOG.md)

Machine-readable schemas live in [`schemas/`](schemas), and frozen runtime
contract baselines live in [`contracts/`](contracts). Documents under
`docs/development`, `docs/changelog`, `docs/releases`, and `docs/validation`
are non-normative engineering records; they may describe older releases. Use
the language, standard-library, CLI, and installation references above for
current behavior.

## Validate a checkout

```sh
./reason ci --json
```

This is the canonical repository validation command used by contributors and
coding agents.

## License

ReasonScript is licensed under the [Apache License 2.0](LICENSE). The
`vscode-extension/` package is separately MIT-licensed.
