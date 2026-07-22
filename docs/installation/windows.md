# Installing on Windows 11

Source installation requires Python 3.11 or newer, Git, and Rust/Cargo. From
PowerShell, run `powershell -ExecutionPolicy Bypass -File scripts/install.ps1 -NonInteractive -Json`.
The default root is `%LOCALAPPDATA%\ReasonScript`; add
its `bin` directory to the user PATH if needed. Prebuilt update packages include
`reason-vision.exe` and do not require Cargo on the target system.
