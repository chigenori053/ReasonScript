# Installing on macOS

The V0.5.5.13 prebuilt package supports Apple Silicon (`arm64`). Download the
ZIP and SHA-256 sidecar from the GitHub Release, verify them with `shasum -a 256
-c`, then pass the ZIP to `reason update --package`.

Source installation requires Python 3.11 or newer, Git, and Rust/Cargo to build
the native ReasonRuntime/crates/vision-core. Run `./scripts/install.sh --non-interactive`; then add
`~/.reasonscript/bin` to `PATH`. A custom root can be selected with `--prefix`
or `REASONSCRIPT_HOME`. Prebuilt update packages already contain the native
ReasonRuntime/crates/vision-core and do not require Cargo on the target system.

Verify with `reason doctor --json` and `reason install-validate --json`. Exit code 1 from doctor means a usable but degraded environment, commonly because optional components or PATH registration are absent.
