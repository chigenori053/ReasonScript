# ReasonScript v0.5.2.4 Installation

## Official artifact

The official macOS arm64 update-and-install package is:

`dist/v0.5.2.4/reasonscript-0.5.2.4-macos-arm64.zip`

The adjacent `.zip.sha256`, `.manifest.json`, and `.manifest.sha256` files are
part of the release unit. Do not distribute the archive without its sidecars.

The package is acceptable only when package inspection reports:

- `package_class: release`
- `dirty: false`
- `freshness.status: fresh` against its recorded source commit
- target `macos/arm64`
- expected version `0.5.2.4`

## Update an existing installation

Run the check before activation:

```sh
reason update --check \
  --package dist/v0.5.2.4/reasonscript-0.5.2.4-macos-arm64.zip \
  --json
```

Apply the update:

```sh
reason update \
  --package dist/v0.5.2.4/reasonscript-0.5.2.4-macos-arm64.zip \
  --json
```

Validate the active installation:

```sh
reason update --validate --json
```

Successful completion requires `installed_version: 0.5.2.4`, no fatal
diagnostics, and passing version, doctor, install-info, install-validate,
scalar, Tensor, loop, project, and RS-GSR-001 through RS-GSR-003 probes.

The official archive SHA-256 is:

```text
7878427a9b2d8b81a5d14ac333417aff51d368cb79dba8dffd92c109ad8f63a4
```

## Recovery

Activation is atomic. If post-install validation fails, the updater restores
the previous healthy version automatically and reports INS-UPD-010 followed by
INS-UPD-011.
