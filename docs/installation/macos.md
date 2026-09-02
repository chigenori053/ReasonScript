# Installing on macOS

Source installation requires Python 3.11 or newer, Git, and Rust/Cargo to build
the native ReasonRuntime/crates/vision-core. Run `./scripts/install.sh --non-interactive`; then add
`~/.reasonscript/bin` to `PATH`. A custom root can be selected with `--prefix`
or `REASONSCRIPT_HOME`. Prebuilt update packages already contain the native
ReasonRuntime/crates/vision-core and do not require Cargo on the target system.

Verify with `reason doctor --json` and `reason install-validate --json`. Exit code 1 from doctor means a usable but degraded environment, commonly because optional components or PATH registration are absent.
