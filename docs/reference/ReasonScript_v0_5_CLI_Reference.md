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
