# ReasonScript v0.5.4.5 Installation

The macOS arm64 update package is `reasonscript-0.5.4.5-macos-arm64.zip`.
Validate it before activation, then update the local installation:

```sh
reason update package-validate <package> --allow-development-package --json
reason update --package <package> --allow-development-package --json
reason --version
```

The development-package option is only required for a locally built package
with dirty-source provenance. A clean release package must be installed without
that option.

## What changed since v0.5.4.4

This update releases Tensor Training Foundation v0.2: NCHW convolution and
pooling, reverse-mode automatic differentiation, tensor slicing/gathering,
seeded random creation, bounded lifecycle management, verified `.rstensor`
persistence, and `reason tensor import`, `inspect`, and `verify` commands.
It also prevents unreachable Tensor backend values from accumulating during
iterative execution, bounds Tensor loop-trace snapshots, improves runtime
diagnostic locations, and accepts scientific-notation numeric literals.
