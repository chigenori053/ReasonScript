# ReasonScript 0.5.2.2 Release Notes

ReasonScript 0.5.2.2 fixes two RUO integration defects found while rebuilding
the Solar System simulator:

- `reason object` now finds the packaged native ReasonUnit Runtime from any
  project directory.
- Python-generated canonical `.ruo` files now pass Rust native record digest
  verification without JSON re-serialization differences.

The release preserves RUO-F1 bytes and logical semantics. Numerical simulation
continues to use `reason run`; Object commands remain structural operations.

## Official package

The official macOS arm64 update-and-install artifact is:

`dist/v0.5.2.2/reasonscript-0.5.2.2-macos-arm64.zip`

It is release-class, built from a clean committed source tree, accompanied by
SHA-256 and provenance sidecars, and validated through both fresh-install and
0.5.2.1-to-0.5.2.2 update workflows.
