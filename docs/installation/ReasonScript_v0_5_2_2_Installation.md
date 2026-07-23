# ReasonScript v0.5.2.2 Installation

## Official artifact

The official macOS arm64 update-and-install package is:

`dist/v0.5.2.2/reasonscript-0.5.2.2-macos-arm64.zip`

The adjacent `.zip.sha256`, `.manifest.json`, and `.manifest.sha256` files are
part of the release unit. Do not distribute the archive without its sidecars.

The package is acceptable only when package inspection reports:

- `package_class: release`
- `dirty: false`
- `freshness.status: fresh` when checked against its recorded source commit
- target `macos/arm64`
- expected version `0.5.2.2`

## Update an existing installation

Run the check before activation:

```sh
reason update --check \
  --package dist/v0.5.2.2/reasonscript-0.5.2.2-macos-arm64.zip \
  --json
```

Apply the update:

```sh
reason update \
  --package dist/v0.5.2.2/reasonscript-0.5.2.2-macos-arm64.zip \
  --json
```

Validate the active installation:

```sh
reason update --validate --json
```

Successful completion requires `installed_version: 0.5.2.2`, no fatal
diagnostics, and `passed` results for version, doctor, install-info,
install-validate, scalar, Tensor, loop, and project validation.

## RUO interoperability smoke

From a project directory unrelated to the installation, run structural Object
operations against a canonical `.ruo` file:

```sh
reason object inspect OBJECT.ruo --json
reason object query OBJECT.ruo --json
reason object project OBJECT.ruo --json
reason object snapshot OBJECT.ruo --json
```

Each command must report `ok: true` and native provenance
`reasonscript-reasonunit-native-runtime/1.0`.

## Recovery

Activation is atomic. If post-install validation fails, the updater restores
the previous healthy version automatically and reports INS-UPD-010 followed by
INS-UPD-011.
