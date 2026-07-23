# ReasonScript RUO Native Interoperability Correction v0.1

Specification ID: `reasonscript-ruo-native-interoperability-correction/0.1`
Status: VALIDATED
Date: 2026-07-24

## Problem

The consolidated Object CLI conflates the caller's project root with the
ReasonScript distribution root. Installed commands therefore search for
`reasonunit-runtime-native` below the current project instead of the active
installation.

The RUO-F1 Python writer hashes canonical JSON bytes for each record body.
The native Rust reader currently parses the body into `serde_json::Value` and
re-serializes it before hashing. Re-serialization is not the RUO-F1
canonicalization contract and can change number spellings, causing
`RUO-N1-007 record digest mismatch`.

## Required behavior

1. Native runtime discovery is rooted at the distribution containing the
   executing toolchain and is independent of the project and current working
   directories.
2. Development discovery retains the distribution-local release and debug
   Cargo targets.
3. `reason object` and `reason reasonunit-runtime` use distribution discovery
   for every native operation.
4. The Rust reader verifies `body_sha256` against the canonical body bytes
   present in the RUO-F1 envelope. It must not hash a re-serialized
   `serde_json::Value`.
5. Invalid JSONL, missing bodies, digest tampering, and malformed seals remain
   rejected as `RUO-N1-007`.
6. Cross-runtime tests cover Python-writer/Rust-reader interoperability,
   including exponent-form floating-point values and VisionRuntime objects.
7. Installed-layout tests invoke Object operations from an unrelated project
   directory.

## Compatibility

The correction does not change RUO-U1 logical semantics, RUO-F1 bytes, stable
IDs, native operation results, or the division of responsibility between
`reason run` numerical evaluation and structural `reason object` operations.

## Acceptance

- Installed `reason object inspect`, `query`, `project`, and `snapshot` resolve
  the packaged native runtime from an arbitrary working directory.
- Python-written canonical RUO-F1 files load in the Rust runtime.
- VisionRuntime output converted by `reasonunit-file write` loads natively.
- Tampered record bodies fail deterministically.
- Rust tests, focused RUO/Vision tests, artifact validation, Golden tests, and
  `reason ci --json` pass.
