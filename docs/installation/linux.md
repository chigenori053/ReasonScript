# Installing on Linux

Source installation requires Python 3.11 or newer, Git, and Rust/Cargo to build
the native VisionRuntime. Run `./scripts/install.sh --non-interactive`; then add
`~/.reasonscript/bin` to `PATH`. The installer is user-scoped and does not
require root privileges or alter shell profiles. Prebuilt update packages do
not require Cargo on the target system.
