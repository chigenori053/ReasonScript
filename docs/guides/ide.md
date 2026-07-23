# IDE Setup

ReasonScript has three editor/IDE-facing surfaces at different levels of
maturity. Pick based on what you need today.

## VS Code Extension (recommended for most users)

`vscode-extension/` is a real, versioned VS Code extension with syntax
highlighting (a TextMate grammar,
`syntaxes/reasonscript.tmLanguage.json`) and LSP integration.

Install from a built `.vsix`, or build it yourself:

```sh
cd vscode-extension
npm install
npm run compile
```

Then load it as an unpacked extension in VS Code (or package it with
`vsce package` and install the `.vsix`).

## Language Server (LSP)

`frontend/lsp/` implements diagnostics, hover, completion, definition,
references, and a symbol index, built on the same parser as the compiler
(see [docs/architecture/compiler.md](../architecture/compiler.md)). Run it
directly:

```sh
python3 -m frontend.lsp
```

Known limitation: the LSP maintains its own lightweight source index
because the AST doesn't yet carry source spans — this is called out in
`docs/platform_architecture_review/lsp_review.md` and tracked as a Beta
goal in [ROADMAP.md](../../ROADMAP.md#beta-planning) ("Refactor LSP symbol
index to compiler source spans"). Expect the symbol index to occasionally
diverge from what the compiler itself would report until that lands.

## IDE Core and Desktop App

`frontend/ide/` is an editor-agnostic core that wraps the `reason` CLI
commands (`build`/`run`/`test`/`check`) with workspace detection and
diagnostics/output-channel plumbing. Today it shells out to the CLI rather
than calling the compiler in-process — sufficient for scripted or
lightweight integrations, but not a low-latency in-process API yet
(`docs/platform_architecture_review/ide_review.md`).

`apps/reasonscript-ide/` is a native desktop app built on this core using
Tauri 2 (Rust backend + React/TypeScript/Vite/Monaco frontend):

```sh
cd apps/reasonscript-ide/ui
npm install
cd ../src-tauri
cargo build
```

See `apps/reasonscript-ide/` for the full Tauri development workflow
(`cargo tauri dev`, etc., if the `tauri-cli` is installed).

## Web Playground

For trying ReasonScript without any local editor setup, see
[installation.md](installation.md#optional-web-playground) — it runs a
Monaco-based editor against a FastAPI backend, without needing VS Code or
the desktop app at all.

## Which One Should I Use?

| You want... | Use |
| --- | --- |
| Syntax highlighting + diagnostics in an editor you already use | VS Code extension |
| To try ReasonScript with zero local install | Web playground |
| A dedicated desktop app | `apps/reasonscript-ide/` |
| To build a new editor integration | `frontend/lsp/` + `frontend/ide/` directly, following the VS Code extension as a reference thin-adapter |

Editor adapters beyond VS Code (e.g. Neovim) are a tracked but unstarted
Beta P2 roadmap item — see [ROADMAP.md](../../ROADMAP.md#beta-planning).
