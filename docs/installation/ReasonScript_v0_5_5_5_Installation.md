# ReasonScript v0.5.5.5 Installation

The macOS arm64 update package is `reasonscript-0.5.5.5-macos-arm64.zip`.
Validate it before activation, then update the local installation:

```sh
reason update package-validate <package> --json
reason update --package <package> --json
reason --version
```

For a locally built package with dirty-source provenance, add
`--allow-development-package`. A clean release package must be installed
without that option.

## What changed since v0.5.5.4

This update hardens strict Rust runtime execution across multi-file packages,
Tensor/autograd calculation lifetimes, optimizer diagnostic locations, trace
handling, artifact schemas, project validation, CLI help, and explicit source
line continuation. It restores the established value-only
`reason run --result-output` contract and machine-readable JSON trace behavior.
