# ReasonScript v0.5.2.2 Release Report

## Completion Summary

ReasonScript v0.5.2.2 packages the validated RUO native interoperability
correction as the official update-and-install maintenance release for macOS
arm64.

## Implemented Features

- Distribution-root native ReasonUnit Runtime discovery.
- Raw canonical RUO-F1 record-body digest verification.
- Python/Rust exponent-number and Vision-derived RUO interoperability.
- Installed arbitrary-project Object CLI operation support.

## Validation Results

- Version consistency: 6/6 PASS.
- Focused RUO-F1/N1/N2/Vision regression: 54 PASS.
- Installed-distribution package tests: 6 PASS.
- Native Rust tests: 5 PASS; Clippy and rustfmt: PASS.
- `reason ci --json`: PASS, 1092 tests.
- Artifact validation, Golden tests, Agent Protocol, and compatibility: PASS.
- Clean release provenance (`package_class: release`, `dirty: false`): PASS.
- Local update from installed 0.5.2.1 to 0.5.2.2: PASS.
- Post-install version, doctor, install-info, install-validate, scalar, Tensor,
  loop, and project probes: PASS.
- Installed Object inspect/query/project/snapshot from an unrelated cwd: PASS.
- Installed native load of a Vision-derived Python-written RUO-F1 file: PASS.

## Generated Artifacts

- `dist/v0.5.2.2/reasonscript-0.5.2.2-macos-arm64.zip`
- `dist/v0.5.2.2/reasonscript-0.5.2.2-macos-arm64.zip.sha256`
- `dist/v0.5.2.2/reasonscript-0.5.2.2-macos-arm64.manifest.json`
- `dist/v0.5.2.2/reasonscript-0.5.2.2-macos-arm64.manifest.sha256`

The sidecars are the canonical source for the final archive digest and source
commit. Package promotion is valid only when those values match the archive
and the clean release commit.

## Compatibility Notes

The update floor remains 0.5.0 and runtime compatibility remains
`>=0.5.0,<0.6.0`. RUO-F1 bytes and logical semantics are unchanged.
The package is formally designated as the ReasonScript 0.5.2.2 macOS arm64
installation package.

## Remaining Work

None.
