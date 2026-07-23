# ReasonScript VSCode Extension Phase 1.2 Report

Schema: reasonscript-vscode/0.1.3  
Date: 2026-06-20  
Status: **Complete**

---

## Summary

Phase 1.2 delivers activation fault isolation for the ReasonScript VSCode extension, resolving the `command 'reasonscript.build' not found` failure identified in `ReasonScript_VSCode_Command_Investigation_Report.md` (VCMD-004).

`reasonscript-0.1.3.vsix` packages cleanly with zero warnings.

---

## Changes

### `vscode-extension/src/extension.ts`

**Root cause fix (Section 5 — Required)**

`await client.start()` is now wrapped in a `try/catch` block. LSP startup failure no longer propagates from `activate()` and does not cause VSCode to dispose `context.subscriptions`.

**Output channel (Section 7)**

A dedicated `"ReasonScript"` output channel is created at activation time. It records:

```
Starting language server...
Language server started.
```

or on failure:

```
Starting language server...
Language server unavailable:
<error message>
Toolchain commands remain available.
```

**Status bar (Section 8)**

The status bar now transitions between three states:

| State | Text |
|---|---|
| Initial | `ReasonScript Ready` |
| LSP started successfully | `ReasonScript LSP Online` |
| LSP failed to start | `ReasonScript LSP Offline` |

**Warning notification (Section 6)**

On LSP failure, `vscode.window.showWarningMessage` is called:

```
ReasonScript: Language server unavailable. <message>
```

**Activation order (preserved)**

```
create statusBar                           ← unchanged
create outputChannel                       ← new
registerToolchainCommands()                ← unchanged; before LSP
registerTaskProvider()                     ← unchanged
outputChannel.appendLine("Starting...")   ← new
try {
  createLanguageClient()
  await client.start()
  statusBar: LSP Online                   ← new
  outputChannel: started                  ← new
} catch (err) {
  statusBar: LSP Offline                  ← new
  outputChannel: unavailable + recovery   ← new
  showWarningMessage(...)                 ← new
}
detectWorkspaceRoot()                      ← unchanged
loadPackageGraph()                         ← unchanged
autoCheck → executeCommand("check")        ← now reachable
```

### `vscode-extension/package.json`

Version bumped: `0.1.2` → `0.1.3`

### `vscode_extension_phase1_tests/test_vscode_extension_phase1_2.py`

New conformance test file. Ten tests, all static analysis of TypeScript source and package manifest.

---

## Conformance Results

### VSXP12 (Phase 1.2 — new)

| ID | Test | Result |
|----|------|--------|
| VSXP12-001 | Activation With LSP Success | ✓ PASS |
| VSXP12-002 | Activation With LSP Failure | ✓ PASS |
| VSXP12-003 | Commands Survive LSP Failure | ✓ PASS |
| VSXP12-004 | Build Command Available | ✓ PASS |
| VSXP12-005 | Check Command Available | ✓ PASS |
| VSXP12-006 | Run Command Available | ✓ PASS |
| VSXP12-007 | Test Command Available | ✓ PASS |
| VSXP12-008 | Warning Notification | ✓ PASS |
| VSXP12-009 | Output Logging | ✓ PASS |
| VSXP12-010 | End-to-End Recovery | ✓ PASS |

**10 / 10 passed**

### Phase 1 Regression (VSX1 + VSXP — unchanged)

| Suite | Tests | Result |
|---|---|---|
| VSX1-001 – VSX1-020 | 20 | ✓ All PASS |
| VSXP-001 – VSXP-004 | 4 | ✓ All PASS |

**24 / 24 passed — zero regressions**

---

## Build Artifacts

| Command | Result |
|---|---|
| `npm run compile` | ✓ Zero errors |
| `npm run package` | ✓ Zero warnings |
| Output | `reasonscript-0.1.3.vsix` (19 files, 16.18 KB) |

---

## Validation Procedure

```
code --install-extension reasonscript-0.1.3.vsix
```

1. Open VSCode in a folder **without** `python3 -m frontend.lsp` available.
2. Open Command Palette → `ReasonScript: Build`
   - Expected: Output channel opens; `WorkspaceNotFound` if no `reason.toml` present
   - Not expected: `command 'reasonscript.build' not found`
3. Check status bar — shows `ReasonScript LSP Offline`
4. Check `Output → ReasonScript` — shows startup failure and recovery message
5. Check notification — warning bubble appears once

6. Open VSCode in a folder **with** LSP available.
7. Verify status bar shows `ReasonScript LSP Online`

---

## Regression Impact Analysis

| Area | Impact |
|---|---|
| Command palette (build/run/test/check) | Fixed — commands execute after LSP failure |
| LSP diagnostics / hover / completion | No change — still requires `python3 -m frontend.lsp` |
| Task provider | No change |
| `autoCheck` behavior | Restored — `executeCommand("reasonscript.check")` now reachable |
| Users with LSP installed | No regression — `try/catch` transparent on success |
| VSIX packaging | No change — 19 files, same structure |

---

## Out of Scope

Per Phase 1.2 specification:

- LSP feature changes
- Toolchain changes
- Compiler / runtime changes
- IDE architecture changes

*Schema: reasonscript-vscode/0.1.3*
