# Installing on Linux

ReasonScript v0.5.5.12 does not provide an official Linux binary package.
Linux is exercised by repository CI, and installation is currently supported
from source only.

Source installation requires Python 3.11 or newer, Git, and Rust/Cargo to build
the native ReasonRuntime/crates/vision-core. Run `./scripts/install.sh --non-interactive`; then add
`~/.reasonscript/bin` to `PATH`. The installer is user-scoped and does not
require root privileges or alter shell profiles.
