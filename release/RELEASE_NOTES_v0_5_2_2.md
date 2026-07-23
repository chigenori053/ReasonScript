# ReasonScript 0.5.2.2 Release Notes

ReasonScript 0.5.2.2 fixes two RUO integration defects found while rebuilding
the Solar System simulator:

- `reason object` now finds the packaged native ReasonUnit Runtime from any
  project directory.
- Python-generated canonical `.ruo` files now pass Rust native record digest
  verification without JSON re-serialization differences.

The release preserves RUO-F1 bytes and logical semantics. Numerical simulation
continues to use `reason run`; Object commands remain structural operations.
