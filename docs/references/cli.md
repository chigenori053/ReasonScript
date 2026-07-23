# CLI Reference

The `reason` command is the ReasonScript toolchain CLI, implemented in
`toolchain/` (Python, no build step required — see
[docs/guides/installation.md](../guides/installation.md)). Invoke it as
`./reason <command> [args]` or `python3 -m toolchain <command> [args]`.

```text
Usage: reason <command> [args]

Commands:
  init <name>   Create a new ReasonScript project
  build         Compile source files
  run           Execute the compiled program
  test          Run test suites
  check         Validate sources without building
```

## `reason init <name>`

Creates a new single-package project directory named `<name>`:

```text
<name>/
  reason.toml
  src/main.rsn
  tests/sample_test.rsn
  target/{ast,ir,metadata,runtime}/
  packages/
```

Fails with `ProjectExists` if the directory already exists. See
[docs/guides/quick-start.md](../guides/quick-start.md) for the generated
file contents.

## `reason build [--package <name>]`

Compiles `.rsn` sources under `src/` through the full pipeline (Surface AST
-> Semantic AST -> Reason IR) and writes artifacts under `target/`. Uses a
sha256 content cache (`.reason_build_cache`) to skip unchanged files. See
[docs/architecture/compiler.md](../architecture/compiler.md).

## `reason run [--package <name>]`

Executes the compiled program. Requires `reason build` to have already
produced `target/ir/*.json` — fails with `NoBuildArtifacts` otherwise.
Dispatches to `RuntimeReal` or `HybridRuntime` based on `reason.toml`'s
`[runtime] backend` (via `frontend.runtime_integration`). See
[docs/architecture/runtime.md](../architecture/runtime.md).

## `reason test [--package <name>]`

Runs the test suite under `tests/`.

## `reason check [--package <name>]`

Validates sources without producing build artifacts — faster feedback loop
for syntax/structural errors while editing. See
[diagnostics.md](diagnostics.md) for the error codes it can surface.

## `--package <name>`

All commands except `init` accept `--package <name>` to scope the command
to a single package once multi-package layout support exists. Today's
projects are single-package, so this is mostly a forward-compatible flag —
see [COMPATIBILITY.md](../../COMPATIBILITY.md#known-limitations-current-alpha).

## Related Commands (Outside `reason`)

These aren't part of the `reason` CLI but are commonly used alongside it:

```sh
# Full build/test matrix across Python + Rust + npm projects
make build
make test
make lint
python3 scripts/test_platform.py build

# Layered conformance certification
python3 conformance/run_conformance.py

# Release/freeze gates (see COMPATIBILITY.md for what each one freezes)
python3 release/v0.1-alpha/run_release_validation.py
python3 release/language-surface-v0.1/run_release_validation.py
python3 release/semantic-language-v0.2/run_release_validation.py

# Validate a Reason IR document against the schema
cargo run --manifest-path HybridRuntime/Cargo.toml \
  --bin reason-ir-validator -- path/to/document.json
```

See [CONTRIBUTING.md](../../CONTRIBUTING.md#build-and-test) for the fuller
contributor-facing command list.
