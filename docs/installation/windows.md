# Installing on Windows 11

Windows support is experimental in ReasonScript v0.5.5.13. No official Windows
package is published, and clean-device certification remains pending.

Source installation requires Python 3.11 or newer, Git, and Rust/Cargo. From
PowerShell, run `powershell -ExecutionPolicy Bypass -File scripts/install.ps1 -NonInteractive -Json`.
The default root is `%LOCALAPPDATA%\ReasonScript`; add its `bin` directory to
the user PATH if needed. This source-install path is not a certified prebuilt
distribution.
