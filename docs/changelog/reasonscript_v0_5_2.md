# ReasonScript v0.5.2

ReasonScript 0.5.2 packages the safe-Rust VisionRuntime, typed `vision.*`
language integration, RUO-T1 Vision Tensor projections, atomic `.ruo`
publication, LSP/IDE support, and the platform-native `reason-vision` command.

The canonical version was advanced from 0.5.1 to 0.5.2 across runtime, CLI,
Python, release, and validation-profile metadata. The macOS arm64 package can
perform both updates and fresh installations. Fresh installation consumes the
prebuilt VisionRuntime and updater without requiring Rust/Cargo on the target.

Validation: version consistency 6/6, installed distribution 36/36, package
self-validation PASS, fresh-install Vision-to-RUO smoke PASS, and canonical CI
PASS with 1,085 tests and 17 compatibility targets.
