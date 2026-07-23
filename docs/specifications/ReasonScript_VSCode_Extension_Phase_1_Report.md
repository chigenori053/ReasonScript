# ReasonScript VSCode Extension Phase 1 Report

Version: `reasonscript-vscode/0.1`

Status: Complete

## Implemented Scope

VSCode Extension Phase 1 adds the first thin editor client for ReasonScript.

Implemented components:

- Extension manifest with official ID `reasonscript.reasonscript`
- `reasonscript` language registration for `.rsn`
- TextMate grammar for keywords, types, runtime APIs, planning APIs, agent APIs,
  world APIs, comments, strings, and numbers
- Language configuration for comments, brackets, and auto-closing pairs
- LSP client startup using `python3 -m frontend.lsp` over STDIO
- Workspace detection for `reason.workspace.toml` and `reason.toml`
- Toolchain commands:
  - `ReasonScript: Build`
  - `ReasonScript: Run`
  - `ReasonScript: Test`
  - `ReasonScript: Check`
- Workspace package argument support through `--package`
- Output channels:
  - `ReasonScript Build`
  - `ReasonScript Run`
  - `ReasonScript Test`
  - `ReasonScript Check`
- Status bar updates for ready, build success/failure, and test success/failure
- Task provider for ReasonScript build, run, test, and check tasks
- PackageGraph loading through the Toolchain/LSP layer
- Configuration keys:
  - `reasonscript.autoCheck`
  - `reasonscript.showTrace`
  - `reasonscript.defaultCommand`

## Thin Client Boundary

The extension does not implement compiler, runtime, planning, or agent logic.
It delegates language intelligence to `frontend.lsp` and execution workflows to
the `reason` toolchain.

## Conformance

Added `vscode_extension_phase1_tests` covering:

- VSX1-001 Extension Activation
- VSX1-002 Workspace Detection
- VSX1-003 Language Registration
- VSX1-004 LSP Startup
- VSX1-005 Diagnostics
- VSX1-006 Hover
- VSX1-007 Completion
- VSX1-008 Definition
- VSX1-009 References
- VSX1-010 Workspace Symbols
- VSX1-011 Build Command
- VSX1-012 Run Command
- VSX1-013 Test Command
- VSX1-014 Check Command
- VSX1-015 Output Channels
- VSX1-016 Status Bar
- VSX1-017 Package Graph Awareness
- VSX1-018 Workspace Project Support
- VSX1-019 Multi-Package Support
- VSX1-020 End-to-End VSCode Workflow

## Validation

Targeted validation:

```text
python3 -m pytest vscode_extension_phase1_tests lsp_phase1_tests toolchain_phase2_tests
60 passed
```

Full repository validation:

```text
python3 -m pytest --import-mode=importlib
666 passed, 2 skipped
```

The repository still has pre-existing duplicate test module basenames that can
interrupt default pytest collection; `--import-mode=importlib` runs the full
suite successfully.

TypeScript packaging requires installing the extension dependencies and then
running:

```text
cd vscode-extension
npm install
npm run compile
npm run package
```
