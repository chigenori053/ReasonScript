# ReasonScript — Development Environment

## Required Tools

| Tool     | Minimum Version | Purpose                          |
|----------|-----------------|----------------------------------|
| Python   | 3.11+           | compiler / analyzer / test runner|
| pytest   | 7.x+            | test execution                   |
| Node.js  | 18.x+           | Playground frontend              |
| npm      | 9.x+            | frontend package management      |
| Rust     | 1.75+           | runtime backend                  |
| Cargo    | bundled w/ Rust | Rust build / fetch               |

### Optional Tools

| Tool   | Purpose                            |
|--------|------------------------------------|
| tauri  | Desktop IDE launch (future phase)  |
| ruff   | Python linting                     |
| mypy   | Python type checking               |

## Environment Check

Before starting development, run:

```bash
python3 scripts/check_environment.py
```

A `[PASS]` result confirms all required tools and paths are present.

## Setup

Install all dependencies:

```bash
python3 scripts/dev.py setup
```

This installs Python dev dependencies, creates the Playground venv, installs frontend npm packages, and fetches Rust crates for every native runtime (`RuntimeReal`, `HybridRuntime`, `RuntimeComplex`, `NativeReasonUnitRuntime`, `ClusterRuntime`, `VisionRuntime`, `VisualizationRuntime`).

Rust test suites run with `cargo test --offline`, so this fetch step must
complete at least once before `reason ci` or `pytest tests` can pass — a
fresh checkout without it fails with unresolved-crate errors such as
`no matching package named 'serde_json' found`.

## Platform

macOS is the primary development platform. Linux is supported for CI.

## Environment Variables

| Variable    | Default | Purpose                              |
|-------------|---------|--------------------------------------|
| PYTHONPATH  | `.`     | Required for pytest and backend      |

The `playground/start.sh` and `dev.py backend` set `PYTHONPATH` automatically.

## Python Virtual Environment

The Playground backend uses a dedicated venv at `playground/.venv`.  
`dev.py setup` creates it automatically.  
`dev.py backend` and `dev.py playground` use it automatically.
