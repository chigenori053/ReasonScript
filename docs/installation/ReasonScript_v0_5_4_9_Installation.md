# ReasonScript v0.5.4.9 Installation

The macOS arm64 update package is
`reasonscript-0.5.4.9-macos-arm64.zip`.

```sh
reason update package-validate <package> --allow-development-package --json
reason update --package <package> --allow-development-package --json
reason --version
reason install-validate --json
```

For a locally built development package, `--allow-development-package` is
required. Successful activation reports version `0.5.4.9`.
