# ReasonScript 0.5.2.4 Release Notes

ReasonScript 0.5.2.4 fixes three defects reported during generic structure
recognition:

- Golden validation is consistent between standalone and canonical CI.
- Compact single-line struct declarations are supported.
- Standard global help invocations exit successfully.

The release preserves multiline struct ASTs, dedicated Phase 8 validation,
unknown-command failures, Golden schemas, and runtime compatibility
`>=0.5.0,<0.6.0`.

## Official package

The official macOS arm64 update-and-install artifact is:

`dist/v0.5.2.4/reasonscript-0.5.2.4-macos-arm64.zip`

Release provenance, SHA-256 values, and local update results are recorded after
the clean-source package build.
