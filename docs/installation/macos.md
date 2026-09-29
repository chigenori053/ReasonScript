# Installing on macOS

The latest published prebuilt package is v0.5.5.15 for Apple Silicon (`arm64`).
Download the ZIP and SHA-256 sidecar from its
[GitHub Release](https://github.com/chigenori053/ReasonScript/releases/tag/v0.5.5.15),
verify them with `shasum -a 256 -c`, then pass the ZIP to
`reason update --package`. For v0.5.6.5 from a clean source checkout, build and
validate a local release-class ZIP before updating:

```sh
python3 scripts/build_update_package.py --version 0.5.6.5 --platform macos --architecture arm64 --format zip --package-class release --out dist
reason update package-validate dist/reasonscript-0.5.6.5-macos-arm64.zip --json
reason update --package dist/reasonscript-0.5.6.5-macos-arm64.zip --json
```

Source installation requires Python 3.11 or newer, Git, and Rust/Cargo to build
the native ReasonRuntime/crates/vision-core. Run `./scripts/install.sh --non-interactive`; then add
`~/.reasonscript/bin` to `PATH`. A custom root can be selected with `--prefix`
or `REASONSCRIPT_HOME`. Prebuilt update packages already contain the native
ReasonRuntime/crates/vision-core and do not require Cargo on the target system.

Verify with `reason doctor --json` and `reason install-validate --json`. Exit code 1 from doctor means a usable but degraded environment, commonly because optional components or PATH registration are absent.
