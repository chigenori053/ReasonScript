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

It is release-class, built from clean source commit
`a5efd93cef592d19d720732dfb00c41a81b86b78`, accompanied by SHA-256 and
provenance sidecars, and validated through the 0.5.2.3-to-0.5.2.4 local update
workflow.
