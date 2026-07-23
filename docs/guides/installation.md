# Installation

ReasonScript is a polyglot repository: the CLI and compiler frontend are
Python, the runtimes are Rust, and the IDE/playground UIs are TypeScript.
There is no packaged installer yet (no PyPI/crates.io/npm publish) — you
run ReasonScript from a checkout of the repository.

## Prerequisites

| Component | Requirement | Needed for |
| --- | --- | --- |
| Python | 3.11+ | The `reason` CLI, compiler frontend, LSP/IDE core, SDK, test suites |
| Rust (`cargo`) | recent stable | Building/running `RuntimeReal`, `HybridRuntime`, `RuntimeComplex`, the desktop IDE shell |
| Node.js + npm | recent LTS | The web playground frontend, the desktop IDE UI, the VS Code extension |

You don't need every toolchain — see the table in
[CONTRIBUTING.md](../../CONTRIBUTING.md#development-setup) for which area
needs which.

There is no root-level dependency manifest (no `requirements.txt`,
`pyproject.toml`, or Cargo workspace file) — each Rust crate has its own
`Cargo.toml`, and Python dependencies for auxiliary services (e.g. the
playground's `fastapi`/`uvicorn`) are installed manually as needed.

## Get the Source

```sh
git clone https://github.com/chigenori053/reasonscript.git
cd reasonscript
```

## Run the CLI Immediately (Python only)

The `reason` CLI is a pure-Python entry point — no build step required:

```sh
./reason --help
# or
python3 -m toolchain --help
```

This is enough to run through [quick-start.md](quick-start.md) end to end.

## Build the Rust Runtimes

Needed if you want to run programs against `RuntimeReal` or `HybridRuntime`
directly, or work on the runtimes themselves:

```sh
cargo build --manifest-path RuntimeReal/Cargo.toml
cargo build --manifest-path HybridRuntime/Cargo.toml
```

## Verify Your Setup

Run the full build/test suite (auto-detects available tools):

```sh
make build
make test
```

Equivalent forms:

```sh
task build   # Taskfile.yml
python3 scripts/test_platform.py build
```

Or run a narrower check:

```sh
python3 conformance/run_conformance.py
```

If a step fails because a toolchain (Go, for instance) isn't installed,
that's expected — see [COMPATIBILITY.md](../../COMPATIBILITY.md#known-limitations-current-alpha)
for the known gaps in cross-language conformance.

## Optional: Web Playground

```sh
cd playground
./start.sh
```

This starts a FastAPI backend (port 8000, expects a Python venv at
`playground/.venv`) and a Vite+React frontend (port 5173). See
`playground/backend/` and `playground/frontend/` for details.

## Optional: VS Code Extension

See `vscode-extension/` — it's a standard VS Code extension project
(`npm install && npm run compile`, or install a published `.vsix`).

## Next Steps

- [quick-start.md](quick-start.md) — run your first ReasonScript program.
- [first-project.md](first-project.md) — a fuller walkthrough with
  `reason init`.
