# ReasonScript v0.5.4.6 Installation

The macOS arm64 update package is `reasonscript-0.5.4.6-macos-arm64.zip`.
Validate it before activation, then update the local installation:

```sh
reason update package-validate <package> --allow-development-package --json
reason update --package <package> --allow-development-package --json
reason --version
```

The development-package option is required only for a local package built from
an uncommitted source tree.

## What changed since v0.5.4.5

This update adds the validated MRA ReasonGraph integration: first-class
relations, canonical RGO-F1 persistence, RUO compatibility projection, native
loading/querying/metadata transactions, MIRP-T1 local exchange, and
capability-gated ReasonScript graph query and transaction operations.
