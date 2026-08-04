# ReasonScript v0.5.4.2 Installation

The macOS arm64 update package is `reasonscript-0.5.4.2-macos-arm64.tar.gz`.
Validate it before activation, then update the local installation:

```sh
reason update package-validate <package> --allow-development-package --json
reason update --package <package> --allow-development-package --json
reason visualization generate --output artifacts/semantic_visualization_runtime/v0_1 --json
```

The development-package option is only required for a locally built package
with dirty-source provenance. A clean release package must be installed without
that option.
