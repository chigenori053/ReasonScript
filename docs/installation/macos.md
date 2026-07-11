# Installing on macOS

Requires Python 3.11 or newer and Git. Run `./scripts/install.sh --non-interactive`; then add `~/.reasonscript/bin` to `PATH`. A custom root can be selected with `--prefix` or `REASONSCRIPT_HOME`.

Verify with `reason doctor --json` and `reason install-validate --json`. Exit code 1 from doctor means a usable but degraded environment, commonly because optional components or PATH registration are absent.
