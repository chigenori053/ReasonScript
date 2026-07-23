# ReasonScript v0.5.2.2 Release Report

## Completion Summary

ReasonScript v0.5.2.2 packages the validated RUO native interoperability
correction as an update-and-install maintenance release.

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

## Generated Artifacts

- `dist/v0.5.2.2/reasonscript-0.5.2.2-macos-arm64.zip`
- Archive SHA-256 sidecar and package provenance manifest sidecars.

## Compatibility Notes

The update floor remains 0.5.0 and runtime compatibility remains
`>=0.5.0,<0.6.0`. RUO-F1 bytes and logical semantics are unchanged.

## Remaining Work

None.
