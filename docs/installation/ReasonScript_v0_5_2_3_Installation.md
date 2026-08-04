# ReasonScript v0.5.2.3 Installation

## Official artifact

The official macOS arm64 update-and-install package is:

`dist/v0.5.2.3/reasonscript-0.5.2.3-macos-arm64.zip`

The adjacent `.zip.sha256`, `.manifest.json`, and `.manifest.sha256` files are
part of the release unit. Do not distribute the archive without its sidecars.

The package is acceptable only when package inspection reports:

- `package_class: release`
- `dirty: false`
- `freshness.status: fresh` against its recorded source commit
- target `macos/arm64`
- expected version `0.5.2.3`

## Update an existing installation

Run the check before activation:

```sh
reason update --check \
  --package dist/v0.5.2.3/reasonscript-0.5.2.3-macos-arm64.zip \
  --json
```

Apply the update:

```sh
reason update \
  --package dist/v0.5.2.3/reasonscript-0.5.2.3-macos-arm64.zip \
  --json
```

Validate the active installation:

```sh
reason update --validate --json
```

Successful completion requires `installed_version: 0.5.2.3`, no fatal
diagnostics, and passing version, doctor, install-info, install-validate,
scalar, Tensor, loop, project, RS-VWM-001, and RS-VWM-002 probes.

The official archive SHA-256 is:

```text
a8300e175ceb84dabcae5b84616a36c5ff785bd230431f67ea2c8c77bd6df5fc
```

## Recovery

Activation is atomic. If post-install validation fails, the updater restores
the previous healthy version automatically and reports INS-UPD-010 followed by
INS-UPD-011.
