# ReasonScript VSCode Extension

Official ReasonScript editor integration for Visual Studio Code.

## Purpose

Provides language support for ReasonScript (`.rsn` files), including syntax highlighting, LSP-based diagnostics, and task integration for build, run, test, and check commands.

## Installation

Install from a `.vsix` file:

```
code --install-extension reasonscript-0.1.7.vsix
```

Or install from the VSCode Marketplace once published.

## Build

```
npm ci
npm run compile
```

## Package

```
npm run package
```

Produces `reasonscript-0.1.7.vsix`. The package command compiles the
extension first, so the VSIX never relies on a stale `out/` directory.

## Run

Open a folder containing a `reason.toml` or `reason.workspace.toml` file. The extension activates automatically on `.rsn` files.

Available commands (via Command Palette):

- `ReasonScript: Build`
- `ReasonScript: Run`
- `ReasonScript: Test`
- `ReasonScript: Check`

## Test

Run TypeScript validation:

```
npm test
```

## Check

Run type checking without emitting output:

```
npm run check
```

## Workspace Support

Multi-root workspaces are supported. When a `reason.workspace.toml` is present, the extension detects and activates workspace mode automatically.

The extension activates on:
- `workspaceContains:reason.toml`
- `workspaceContains:reason.workspace.toml`
