# ReasonScript v0.5.4.3 Installation

The macOS arm64 update package is `reasonscript-0.5.4.3-macos-arm64.zip`.
Validate it before activation, then update the local installation:

```sh
reason update package-validate <package> --allow-development-package --json
reason update --package <package> --allow-development-package --json
reason visualization generate --output artifacts/semantic_visualization_runtime/v0_1 --json
```

The development-package option is only required for a locally built package
with dirty-source provenance. A clean release package must be installed without
that option.

## What changed since v0.5.4.2

Adds `reason view`, a terminal CodeViewer for browsing a `.rsn` source file
alongside its compiled Surface AST, Semantic AST, Reason IR, and
ExecutionPlan. See
[`docs/reference/ReasonScript_v0_5_CLI_Reference.md`](../reference/ReasonScript_v0_5_CLI_Reference.md#codeviewer)
and [`CHANGELOG.md`](../../CHANGELOG.md) for details.
