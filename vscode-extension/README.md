# ReasonScript VSCode Extension

Official ReasonScript editor integration for Visual Studio Code.

## Purpose

Provides language support for ReasonScript (`.rsn` files), including syntax highlighting, LSP-based diagnostics, and task integration for build, run, test, and check commands.

## Installation

Install from a `.vsix` file:

```
code --install-extension reasonscript-0.1.2.vsix
```

Or install from the VSCode Marketplace once published.

## Build

```
npm install
npm run compile
```

## Package

```
npm run package
```

Produces `reasonscript-0.1.2.vsix`.

## Run

Open a folder containing a `reason.toml` or `reason.workspace.toml` file. The extension activates automatically on `.rsn` files.

Available commands (via Command Palette):

- `ReasonScript: Build`
- `ReasonScript: Run`
- `ReasonScript: Test`
- `ReasonScript: Check`

## Test

Run the extension test suite:

```
npm test
```

## Check

Run type checking without emitting output:

```
npx tsc --noEmit
```

## Workspace Support

Multi-root workspaces are supported. When a `reason.workspace.toml` is present, the extension detects and activates workspace mode automatically.

The extension activates on:
- `workspaceContains:reason.toml`
- `workspaceContains:reason.workspace.toml`
