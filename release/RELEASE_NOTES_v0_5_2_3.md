# ReasonScript 0.5.2.3 Release Notes

ReasonScript 0.5.2.3 fixes two language defects reported during
VisionWorldModel V0 development:

- Composed calls such as `Outer(Inner(1))` now evaluate and lower in the
  correct order without duplicate `transition_id` values.
- Typed function parameter lists may be formatted across multiple lines.

The release preserves canonical function return IDs, established branch
evidence, Reason IR compatibility, and runtime compatibility
`>=0.5.0,<0.6.0`.

## Official package

The official macOS arm64 update-and-install artifact is:

`dist/v0.5.2.3/reasonscript-0.5.2.3-macos-arm64.zip`

It is release-class, built from clean source commit
`2c0df336dc137a8b43fffbf94294766a7e08e7bd`, accompanied by SHA-256 and
provenance sidecars, and validated through the 0.5.2.2-to-0.5.2.3 update
workflow.
