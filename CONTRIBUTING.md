# Contributing to ReasonScript

Thanks for your interest in contributing. ReasonScript is an early-stage
(`0.1.0-alpha`) project, so expect interfaces below the frozen list in
[COMPATIBILITY.md](COMPATIBILITY.md) to move quickly.

By contributing, you agree that your contributions are licensed under the
[Apache License 2.0](LICENSE) (see [NOTICE](NOTICE)), and you agree to
abide by the [Code of Conduct](CODE_OF_CONDUCT.md).

## Before You Start

- Read [docs/architecture/overview.md](docs/architecture/overview.md) to
  understand which subsystem (Compiler, Runtime, ReasonUnit, WorldModel,
  SDK, LSP/IDE, Toolchain) your change touches.
- Check [ROADMAP.md](ROADMAP.md) and open issues/PRs to avoid duplicate work.
- For anything that changes a **frozen interface** (see
  [COMPATIBILITY.md](COMPATIBILITY.md#frozen-interfaces)), open an issue or
  a proposal doc first — see [GOVERNANCE.md](GOVERNANCE.md#decision-making).

## Development Setup

ReasonScript is a polyglot repository: the CLI and compiler frontend are
Python, the runtimes are Rust, and the IDE/playground UIs are TypeScript.
You don't need every toolchain to work on every part of the project.

| You're changing... | You need |
| --- | --- |
| `toolchain/`, `frontend/` (compiler, LSP, IDE core), `sdk/`, tests under `*_tests/` | Python 3.11+ |
| `HybridRuntime/`, `RuntimeReal/`, `RuntimeComplex/`, `Test/`, `TestPlayground/`, `apps/reasonscript-ide/src-tauri/` | Rust (`cargo`) |
| `playground/frontend/`, `apps/reasonscript-ide/ui/`, `vscode-extension/` | Node.js + npm |

There is no single top-level dependency manifest; each Rust crate has its
own `Cargo.toml` and there is no root Python requirements file, so install
what the area you're touching needs (e.g. `fastapi`, `uvicorn` for the
playground backend).

### Build and test

The canonical entry point is `scripts/test_platform.py`, wired to both
`Makefile` and `Taskfile.yml`:

```sh
make build          # or: task build / python3 scripts/test_platform.py build
make test            # or: task test  / python3 scripts/test_platform.py test
make lint
```

Targeted commands you'll use often:

```sh
# Rust crate tests
cargo test --manifest-path HybridRuntime/Cargo.toml
cargo test --manifest-path RuntimeReal/Cargo.toml

# Python spec/conformance suites (each *_tests/ directory is a unittest suite)
python3 -m unittest discover -s language_spec_validation_tests -p 'test_*.py' -v
python3 -m unittest discover -s operational_semantics_tests -p 'test_*.py' -v

# Full conformance framework
python3 conformance/run_conformance.py

# Release/freeze gates (run before touching a frozen interface)
python3 release/v0.1-alpha/run_release_validation.py
python3 release/language-surface-v0.1/run_release_validation.py
python3 release/semantic-language-v0.2/run_release_validation.py
```

See [docs/guides/installation.md](docs/guides/installation.md) for full
setup instructions and [docs/references/cli.md](docs/references/cli.md) for
the `reason` CLI.

## Making Changes

1. Fork/branch from the default branch.
2. Keep changes scoped: a bug fix doesn't need an accompanying refactor.
3. Add or update tests in the matching `*_tests/` directory, Rust crate
   `tests/`, or `conformance/` layer. Every existing spec doc under
   `docs/specifications/` has a matching test suite — follow that pattern
   for new specs.
4. If you change or add a specification, put it under
   `docs/specifications/` and link it from
   [docs/architecture/overview.md](docs/architecture/overview.md) or the
   relevant `docs/language/` page.
5. Update [CHANGELOG.md](CHANGELOG.md) under an "Unreleased" heading for
   user-visible changes.
6. Run the relevant build/test commands above before opening a PR.

### Commit messages

Write commit messages that explain *why*, not just *what*. Look at
`git log` for the project's existing style.

### Pull requests

- One logical change per PR.
- Describe what changed and why; link related issues.
- CI (build + test + conformance, per `scripts/test_platform.py`) must pass.
- A maintainer will review; see [GOVERNANCE.md](GOVERNANCE.md) for how
  merge decisions are made.

## Reporting Bugs

Open a GitHub Issue with:

- A minimal `.rsn` reproduction or failing command.
- Expected vs. actual behavior, including full error/diagnostic output
  (see [docs/references/diagnostics.md](docs/references/diagnostics.md)).
- Your environment: `reason` version (`VERSION` file), `python3 --version`,
  `rustc --version` if relevant.

Security vulnerabilities: follow [SECURITY.md](SECURITY.md) instead — do
not open a public issue.

## Proposing Language or Runtime Changes

Non-trivial changes to the language surface, Reason IR, or runtime
semantics should start as a short proposal document (an issue is fine for
small changes; a doc under `docs/specifications/` mirroring the existing
`*_v1.md`/`*_Specification_v0.1.md` style is expected for larger ones)
before implementation. This mirrors how existing features
(pattern guards, or-patterns, struct pattern matching, and so on) were
introduced — each has a spec in `docs/specifications/` plus a corresponding
test suite.

## Style

- Python: match existing formatting in `frontend/`, `toolchain/`, `sdk/`
  (the project uses `black`/`ruff`/`mypy` where configured — run
  `make lint` to check).
- Rust: standard `rustfmt`/`clippy` conventions.
- Docs: plain Markdown, one sentence per line is not required, but keep
  lines reasonably short and prefer tables for structured comparisons (see
  existing docs under `docs/` for the house style).
