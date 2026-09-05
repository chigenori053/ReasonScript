# Installing ReasonScript

## Requirements

Source installation requires Python 3.11 or newer, Git, and Rust/Cargo. The
installer is user-scoped and does not require administrator access on macOS or
Linux.

## macOS and Linux

```sh
git clone https://github.com/chigenori053/ReasonScript.git
cd ReasonScript
./scripts/install.sh --non-interactive
```

The default binary directory is `~/.reasonscript/bin`. Add it to `PATH` if the
installer asks you to do so. A custom installation root can be selected with
`--prefix` or `REASONSCRIPT_HOME`.

Platform notes: [macOS](macos.md) and [Linux](linux.md).

## Windows 11

From PowerShell:

```powershell
git clone https://github.com/chigenori053/ReasonScript.git
Set-Location ReasonScript
powershell -ExecutionPolicy Bypass -File scripts/install.ps1 -NonInteractive -Json
```

The default root is `%LOCALAPPDATA%\ReasonScript`. Add its `bin` directory to
your user `PATH` if needed. See [Windows notes](windows.md).

## Verify

```sh
reason --version
reason doctor --json
reason install-validate --json
```

`reason doctor` exit code 1 can indicate a usable but degraded setup, such as a
missing optional component or `PATH` entry. Read its structured diagnostics
before reinstalling.

## Maintenance

- [Troubleshooting](troubleshooting.md)
- [Uninstall](uninstall.md)
- `reason update --help` for update-package operations
