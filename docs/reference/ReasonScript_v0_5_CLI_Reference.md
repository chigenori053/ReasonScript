# ReasonScript v0.5 CLI Reference

## Canonical CI

```sh
./reason ci --json
```

Runs the canonical v0.5 validation pipeline.

## Phase 8 Golden Validation

```sh
./reason phase8-golden validate --json
```

Validates Phase 8 golden fixtures and generated reasoning artifacts.

```sh
./reason phase8-golden update --json
```

Controlled maintenance command. Use only when intentionally updating approved golden artifacts after a specification, compatibility policy, or intentional behavior change.

## ReasoningModel

```sh
./reason reasoning-model validate <file> --json
```

Validates a `reasonscript-reasoning-model/1.0` artifact.

## ReasoningEvaluationReport

```sh
./reason reasoning-eval evaluate <reasoning-model.json> --json
./reason reasoning-eval validate <evaluation-report.json> --json
```

Evaluates a ReasoningModel or validates an existing `reasonscript-reasoning-evaluation-report/1.0` artifact.

## ReasoningRuntimeResult

```sh
./reason reasoning-runtime run <source.rsn> --json
./reason reasoning-runtime build-model <source.rsn> --json
./reason reasoning-runtime evaluate <source.rsn> --json
./reason reasoning-runtime validate <runtime-result.json> --json
```

Generates, evaluates, or validates Phase 8 runtime reasoning artifacts.

## Tensor data files

```sh
./reason tensor import --from json --input data.json --output data.rstensor
./reason tensor import --from csv --input data.csv --output data.rstensor --dtype f32
./reason tensor import --from npy --input data.npy --output data.rstensor
./reason tensor inspect data.rstensor --json
./reason tensor verify data.rstensor --json
```

`reason tensor import` converts rectangular JSON arrays, CSV rows, or NumPy
arrays into the canonical checksum-bearing `.rstensor` profile. NumPy import
requires the optional `numpy` package; JSON and CSV import are dependency-free.
Existing output files are rejected unless `--overwrite` is supplied.

ReasonScript source reads and writes these files with `tensor.load` and
`tensor.save`. Runtime file access remains opt-in:

```sh
./reason run train.rsn --allow-read --allow-write --json
```

Paths are resolved relative to the source file directory and cannot be absolute
or escape that resource root.

## CodeViewer

```sh
./reason view <source.rsn>
./reason view <source.rsn> --stage ir
./reason view <source.rsn> --plain --stage plan --width 100
./reason view <source.rsn> --json
./reason view <project-directory>       # browse a project's file tree instead
./reason view                            # same, rooted at the current directory
```

Browses a `.rsn` source file alongside its compiled Surface AST, Semantic
AST, Reason IR, and ExecutionPlan, correlating whichever declaration
contains the cursor with the stage nodes that came from it. See
[`docs/development/code_viewer_design.md`](../development/code_viewer_design.md)
for the full design.

Passing a directory (or nothing at all) instead of a file opens the
interactive UI straight into the file-tree overlay, scoped to that
directory, with a shallow `.rsn` file auto-opened underneath so there's
always something to look at while picking a different one.

Options:

- `--stage <source|surface|semantic|ir|plan>` — stage shown first (default
  `source`).
- `--module <name>` — select a module when the source declares more than
  one (default: the first module).
- `--root <dir>` — scope the file-tree overlay to `<dir>` regardless of
  which file was opened (default: the file's own directory isn't used —
  the tree is rooted at the current directory, or at the directory
  argument itself when one was given).
- `--json` — print the full compiled-stage document as JSON and exit; the
  shape is validated by `schemas/code_viewer_document.schema.json`. Requires
  a specific file — a directory or omitted path exits with `CV-007`.
- `--plain` — print one static, non-interactive rendering and exit; useful
  for CI logs and coding agents. `--width <n>` bounds its line length
  (default: the terminal width, or 80). Same file requirement as `--json`.

With no `--json`/`--plain` flag, `reason view` opens an interactive
terminal UI when attached to a real terminal:

| Key | Action |
| --- | --- |
| `1`–`5`, `Tab` / `Shift-Tab` | Switch stage |
| `j`/`k`, `↓`/`↑` | Move the cursor (source pane) or the selection (stage/tree pane) |
| `Ctrl-d` / `Ctrl-u` | Half-page scroll |
| `n` / `p` | Jump to the next/previous declaration — or the next/previous search match once `/` has been used |
| `/` | Search the source text; `Enter` confirms, `Esc` cancels |
| `Enter` | Focus the stage pane |
| `Esc` | Clear an active search, otherwise return focus to the source pane |
| `y` | Copy the selected stage node's JSON pointer to the clipboard |
| `d` | Toggle a summary of every stage's diagnostics |
| `e` | Toggle the file-tree overlay for the current project |
| `?` | Toggle this key list |
| `q`, `Ctrl-c` | Quit |

While the file tree is open (`e`): `j`/`k` move, `l`/`Enter` opens a file
or expands a directory, `h` collapses a directory (or jumps to its
parent), and `Esc` closes the tree without changing the open file. The
file currently open is always highlighted, and reopening the tree
re-reveals wherever that file is, even after browsing elsewhere.

Non-interactive environments (a pipe, a CI job, an agent) automatically get
the `--plain` rendering instead of the terminal UI, even without passing
`--plain` explicitly — this only applies when a specific file was given;
with a directory or no path, non-interactive environments get the usage
message instead (there's nothing to render non-interactively without a
file).

**Windows**: the interactive UI needs the `windows-curses` package, pulled
in by installing the `viewer` or `full` extra (`pip install
'reasonscript[viewer]'`). Without it, `reason view` still works — it falls
back to the `--plain` rendering and prints a note to stderr instead of
failing.

## Project Management and Manifest Contract

### Project Initialization (`reason init`)

```sh
reason init <project-name>
```

Initializes a standard ReasonScript project structure:

- `.gitignore` (excludes `target/` and artifacts except `.gitkeep`)
- `artifacts/.gitkeep`
- `README.md`
- `reason.toml` (canonical project manifest)
- `src/main.rsn` (standard entry point)
- `tests/sample_test.rsn` (standard unit test)

### Project Manifest (`reason.toml`)

Standard sections and keys in `reason.toml`:

```toml
[package]
name = "my_project"
version = "0.1.0"
identifier = "my_project"      # normalized package identifier

[project]
name = "my_project"            # defaults to package.name
version = "0.1.0"              # defaults to package.version
reason_version = ">=0.5.0"     # compatible toolchain constraint

[source]
entry = "src/main.rsn"         # entry file (relative, within project root)

[artifacts]
directory = "artifacts"        # artifact output directory (relative, within project root)

[compiler]
language_core = "0.7"          # language core version
platform = "0.2"               # platform version

[runtime]
backend = "RuntimeReal"        # "RuntimeReal" or "HybridRuntime"
max_call_depth = 100           # optional positive integer recursion limit

[dependencies]
# package dependencies

[capabilities]
# capability declarations
```

`[source]` is optional for legacy manifests. When it is absent, `build`,
`check`, `run`, and project validation recursively discover `src/**/*.rsn`
without requiring `src/main.rsn`. When `[source]` is present, `entry` is
required, must remain inside the project root, is compiled first, and does
not exclude sibling modules under `src/`.

#### Diagnostic Policy:
- Truly unknown sections outside known tables (`package`, `project`, `source`, `artifacts`, `compiler`, `runtime`, `dependencies`, `capabilities`) emit `UserWarning: Unknown sections in reason.toml: <sections>`.
- Unknown keys within known sections emit `UserWarning: Unknown keys in reason.toml [<section>]: <keys>`.
- Missing required fields, type errors, or root-escaping paths in `source.entry` / `artifacts.directory` raise `ManifestError`.
- A declared but missing `source.entry` produces `SourceEntryMissing` consistently across `build`, `check`, `run`, and project validation.
