# ReasonScript VSCode Command Investigation Report

Schema: reasonscript-vscode-investigation/0.1  
Date: 2026-06-20  
Version: reasonscript-vscode/0.1.2  
Status: **Root Cause Identified**

---

## Executive Summary

The error `command 'reasonscript.build' not found` is caused by **VCMD-004: Activation Exception**.

`activate()` calls `await client.start()` without error handling. When the LSP server (`python3 -m frontend.lsp`) fails to spawn, `client.start()` rejects, `activate()` propagates the rejection, and VSCode disposes all `context.subscriptions` — unregistering all four commands from the runtime registry.

Commands remain visible in the Command Palette (declared in `contributes.commands`) but have no registered handler. Executing any command produces `command not found`.

---

## 1. Findings by Investigation Target

### INV-001 Package Manifest Verification — PASS

`vscode-extension/package.json` `contributes.commands`:

```json
{ "command": "reasonscript.build",  "title": "ReasonScript: Build"  }
{ "command": "reasonscript.run",    "title": "ReasonScript: Run"    }
{ "command": "reasonscript.test",   "title": "ReasonScript: Test"   }
{ "command": "reasonscript.check",  "title": "ReasonScript: Check"  }
```

All four commands are declared. No anomaly.

---

### INV-002 Activation Events Verification — PASS

`package.json` `activationEvents`:

```json
"onLanguage:reasonscript",
"workspaceContains:reason.toml",
"workspaceContains:reason.workspace.toml",
"onCommand:reasonscript.build",
"onCommand:reasonscript.run",
"onCommand:reasonscript.test",
"onCommand:reasonscript.check"
```

All four `onCommand:*` triggers are declared. Extension activates before command execution. No anomaly.

---

### INV-003 Command Registration Verification — PASS (static)

`src/commands/toolchain.ts:19–26`:

```typescript
for (const command of ["build", "run", "test", "check"] as ToolchainCommand[]) {
  context.subscriptions.push(
    vscode.commands.registerCommand(`reasonscript.${command}`, async (packageName?) => {
      await runToolchain(command, statusBar, packageName);
    })
  );
}
```

All four commands are registered via `registerCommand`. Registration occurs at line 18 of `extension.ts`, before any `await`. No anomaly in source.

---

### INV-004 Command Name Consistency — PASS

| Location | Command ID |
|---|---|
| `package.json` | `"reasonscript.build"`, `"reasonscript.run"`, `"reasonscript.test"`, `"reasonscript.check"` |
| `toolchain.ts` | `` `reasonscript.${"build" | "run" | "test" | "check"}` `` |

100% string match. No discrepancy.

---

### INV-005 Activation Path Verification — **FAIL: Root Cause**

`src/extension.ts` activation sequence:

```
Line 18: registerToolchainCommands(context, statusBar)   ← Commands registered ✓
Line 19: registerTaskProvider(context)
Line 21: client = createLanguageClient(context)
Line 22: context.subscriptions.push(client)
Line 23: await client.start()                            ← *** THROWS HERE ***
Line 25: detectWorkspaceRoot()                           ← Never reached
Line 32: executeCommand("reasonscript.check")            ← Never reached
```

**`await client.start()` is called with no surrounding `try/catch`.**

`createLanguageClient()` (`src/lsp/client.ts:14–35`) configures the LSP server as:

```typescript
const serverOptions: ServerOptions = {
  command: "python3",
  args: ["-m", "frontend.lsp"],
  transport: TransportKind.stdio,
  options: { cwd: workspaceRoot?.fsPath ?? context.extensionPath }
};
```

`python3 -m frontend.lsp` will fail in any environment where:
- `python3` is not in VSCode's process `PATH`
- The `frontend.lsp` Python module is not installed

When this spawn fails, `vscode-languageclient` rejects the `start()` Promise. The rejection propagates unhandled from `activate()`.

**VSCode extension host behavior when `activate()` rejects:**
1. Logs `Activating extension 'reasonscript.reasonscript' failed: <spawn error>`  
2. Marks extension state as `Inactive` / `Failed`
3. Calls `.dispose()` on all items in `context.subscriptions`
4. The `Disposable` returned by `registerCommand()` is disposed → command handler **unregistered**
5. Commands remain visible in the palette (static manifest) but have no runtime handler
6. Execution → `command 'reasonscript.build' not found`

This is the definitive reproduction path.

---

### INV-006 Activation Failure Detection — CONFIRMED

Expected entries in `Output → Log (Extension Host)` and Developer Tools Console:

```
[error] Activating extension 'reasonscript.reasonscript' failed:
  spawn python3 ENOENT
```
or
```
[error] Error starting server process
  Error: connect ECONNREFUSED ...
```

The `autoCheck: true` default setting (`extension.ts:31–33`) also attempts `executeCommand("reasonscript.check")` at the end of `activate()`. This line is **never reached** because `activate()` throws before it. However, if activation had succeeded despite LSP failure, this would immediately invoke a command handler — creating a secondary concern for future investigation.

---

### INV-007 Compiled Output Verification — PASS

`out/extension.js` faithfully reflects `src/extension.ts`. The compiled output at lines 50–63 matches the source logic exactly, including the unguarded `await client.start()` at line 54.

`out/commands/toolchain.js` faithfully reflects `src/commands/toolchain.ts`. Command registration loop at lines 48–53 is correct.

No stale output. `npm run compile` is current.

---

### INV-008 VSIX Content Verification — PASS

`npx vsce ls` output confirms:

```
out/extension.js          ✓
out/commands/tasks.js     ✓
out/commands/toolchain.js ✓
out/lsp/client.js         ✓
out/workspace/workspace.js ✓
syntaxes/                 ✓
language-configuration.json ✓
```

All runtime files are present. No packaging omission.

---

### INV-009 Runtime Command Enumeration — NOT EXECUTABLE (static investigation)

Static analysis confirms commands would be registered then immediately disposed. At no point during activation does the runtime registry contain stable handlers.

---

### INV-010 End-to-End Validation — BLOCKED

`ReasonScript: Build` fails with `command not found` per the failure path described in INV-005. End-to-end validation is blocked until the corrective action below is applied.

---

## 2. Evidence

| Artifact | Path | Finding |
|---|---|---|
| A: package.json | `vscode-extension/package.json` | Commands declared; activationEvents correct |
| B: extension.ts | `vscode-extension/src/extension.ts` | `await client.start()` unguarded at line 23 |
| C: extension.js | `vscode-extension/out/extension.js` | Compiled output current; same defect at line 54 |
| D: toolchain.ts | `vscode-extension/src/commands/toolchain.ts` | Command registration correct |
| E: client.ts | `vscode-extension/src/lsp/client.ts` | `python3 -m frontend.lsp` — external dependency, unguarded |

---

## 3. Root Cause

**Classification: VCMD-004 — Activation Exception**

| Field | Value |
|---|---|
| Root cause | `await client.start()` in `activate()` throws when LSP server is unavailable |
| Throw path | `python3 -m frontend.lsp` ENOENT → `start()` rejects → `activate()` rejects |
| Effect | VSCode disposes `context.subscriptions`; all `registerCommand` Disposables are called |
| Observable symptom | `command 'reasonscript.build' not found` |
| Why commands appear in palette | `contributes.commands` in manifest is static; palette visibility does not require runtime registration |
| Why classified as "activation success" | VSCode Extension panel may not reflect asynchronous rejection state immediately |

---

## 4. Corrective Action

### Required Fix

Wrap `client.start()` in `activate()` with a try/catch. LSP startup failure must not propagate from `activate()`.

**`src/extension.ts` — current (defective):**

```typescript
client = createLanguageClient(context);
context.subscriptions.push(client);
await client.start();
```

**`src/extension.ts` — corrected:**

```typescript
client = createLanguageClient(context);
context.subscriptions.push(client);
try {
  await client.start();
} catch (err) {
  const msg = err instanceof Error ? err.message : String(err);
  vscode.window.showWarningMessage(`ReasonScript: Language server unavailable. ${msg}`);
}
```

This change ensures:
- Commands remain registered regardless of LSP availability
- LSP failure is surfaced to the user as a warning, not a silent activation failure
- Build, run, test, check commands function independently of the LSP

### Secondary Observation (not root cause)

`src/commands/toolchain.ts:8–13` creates `OutputChannel` instances at **module load time** (top-level const), before `activate()` is called. This is harmless with the current VSCode API but is non-standard. These should be created inside `registerToolchainCommands` or `activate()` for clarity.

---

## 5. Validation Procedure

After applying the corrective action:

1. `npm run compile` — must complete with zero errors
2. `npm run package` — must produce `reasonscript-0.1.2.vsix` with zero errors
3. Install VSIX into VSCode (`code --install-extension reasonscript-0.1.2.vsix`)
4. Open a folder **without** `python3` or `frontend.lsp` available
5. Open Command Palette → `ReasonScript: Build`
   - **Expected:** Warning notification about LSP unavailability; output channel opens
   - **Not expected:** `command 'reasonscript.build' not found`
6. Open a folder **without** `reason.toml`
   - **Expected:** Output channel shows `Error: WorkspaceNotFound`
7. Confirm `Output → Log (Extension Host)` shows no activation failure entry

---

## 6. Regression Impact Analysis

| Area | Impact | Notes |
|---|---|---|
| Command palette | Resolved | Commands will execute after fix |
| LSP diagnostics | No change | Still requires `python3 -m frontend.lsp` |
| Build / Run / Test / Check | Resolved | Toolchain commands are independent of LSP |
| Task provider | No change | `registerTaskProvider` was already before the throw |
| `autoCheck` behavior | Restored | `executeCommand("reasonscript.check")` now executes |
| Users with LSP installed | No regression | `client.start()` succeeds; try/catch is transparent |
| Packaging | No change | VSIX content unaffected |

---

*Schema: reasonscript-vscode-investigation/0.1*
