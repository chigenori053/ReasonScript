# ReasonScript

ReasonScript is a reasoning-first programming language and native runtime for
deterministic, inspectable AI workflows. A `.rsn` source file is parsed and
validated, lowered through semantic and computation IR, and executed by the
Rust runtime host.

Current release: **v0.5.5.10** (language core `0.7`).

## Install

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

See the [installation guide](docs/installation/README.md) for macOS, Linux,
Windows, updates, troubleshooting, and removal.

## Try the language

```reason
module Hello {
  fn Double(value: int) -> int {
    return value * 2
  }

  calculation Answer -> int {
    result = Double(21)
  }
}
```

Save this as `hello.rsn`, then run:

```sh
reason check hello.rsn
reason run hello.rsn --json
```

To create a project instead:

```sh
reason init my-project
cd my-project
reason build
reason run
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
- [Changelog](CHANGELOG.md)

Machine-readable schemas live in [`schemas/`](schemas), and frozen runtime
contract baselines live in [`contracts/`](contracts). Historical development
plans, implementation reports, and validation narratives are intentionally not
part of the public documentation set; Git history remains the source for that
material.

## Validate a checkout

```sh
./reason ci --json
```

This is the canonical repository validation command used by contributors and
coding agents.

## License

ReasonScript is licensed under the [Apache License 2.0](LICENSE). The
`vscode-extension/` package is separately MIT-licensed.
