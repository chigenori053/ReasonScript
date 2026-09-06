import * as vscode from "vscode";
import { LanguageClient } from "vscode-languageclient/node";

import { registerToolchainCommands } from "./commands/toolchain";
import { registerTaskProvider } from "./commands/tasks";
import { createLanguageClient } from "./lsp/client";
import { loadPackageGraph } from "./workspace/packageGraph";
import { detectWorkspaceRoot, resolveReasonExecutable } from "./workspace/workspace";

let client: LanguageClient | undefined;

async function stopLanguageServer(): Promise<void> {
  if (client) {
    try {
      await client.stop();
    } catch {
      // Ignore errors on shutdown
    }
    client = undefined;
  }
}

export async function activate(context: vscode.ExtensionContext): Promise<void> {
  console.log("[ReasonScript] activate start");
  const statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
  statusBar.text = "ReasonScript Ready";
  statusBar.show();
  context.subscriptions.push(statusBar);

  const outputChannel = vscode.window.createOutputChannel("ReasonScript");
  context.subscriptions.push(outputChannel);

  registerToolchainCommands(context, statusBar);
  registerTaskProvider(context);

  // Register restartServer command
  context.subscriptions.push(
    vscode.commands.registerCommand("reasonscript.restartServer", async () => {
      outputChannel.appendLine("Restarting ReasonScript Language Server...");
      statusBar.text = "ReasonScript: Restarting LSP...";
      await stopLanguageServer();
      try {
        client = createLanguageClient(context);
        context.subscriptions.push(client);
        await client.start();
        statusBar.text = "ReasonScript LSP Online";
        outputChannel.appendLine("Language server restarted successfully.");
        vscode.window.showInformationMessage("ReasonScript Language Server restarted.");
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        statusBar.text = "ReasonScript LSP Offline";
        outputChannel.appendLine(`Language server restart failed:\n${msg}`);
        vscode.window.showErrorMessage(`ReasonScript Language Server failed to restart: ${msg}`, "Open Settings").then((selection) => {
          if (selection === "Open Settings") {
            vscode.commands.executeCommand("workbench.action.openSettings", "reasonscript");
          }
        });
      }
    })
  );

  console.log("[ReasonScript] commands registered");

  outputChannel.appendLine("Starting language server (reason lsp --stdio)...");
  const resolved = resolveReasonExecutable();
  outputChannel.appendLine(`Resolved ReasonScript executable: ${resolved.path} (source: ${resolved.source}, exists: ${resolved.exists})`);

  if (!resolved.exists) {
    statusBar.text = "ReasonScript: No Executable";
    outputChannel.appendLine("ReasonScript executable not found.");
    vscode.window
      .showErrorMessage(
        `ReasonScript executable not found (${resolved.path}). Please configure 'reasonscript.executablePath' or install ReasonScript to your PATH.`,
        "Open Settings",
        "View Output"
      )
      .then((selection) => {
        if (selection === "Open Settings") {
          vscode.commands.executeCommand("workbench.action.openSettings", "reasonscript.executablePath");
        } else if (selection === "View Output") {
          outputChannel.show(true);
        }
      });
  }

  try {
    console.log("[ReasonScript] lsp startup");
    client = createLanguageClient(context);
    context.subscriptions.push(client);
    await client.start();
    statusBar.text = "ReasonScript LSP Online";
    outputChannel.appendLine("Language server started.");
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    statusBar.text = "ReasonScript LSP Offline";
    outputChannel.appendLine(`Language server unavailable:\n${msg}`);
    outputChannel.appendLine("Toolchain commands remain available.");
    vscode.window
      .showWarningMessage(
        `ReasonScript: Language server unavailable. ${msg}`,
        "Restart Server",
        "Open Settings",
        "View Output"
      )
      .then((selection) => {
        if (selection === "Restart Server") {
          vscode.commands.executeCommand("reasonscript.restartServer");
        } else if (selection === "Open Settings") {
          vscode.commands.executeCommand("workbench.action.openSettings", "reasonscript");
        } else if (selection === "View Output") {
          outputChannel.show(true);
        }
      });
  }

  const workspaceRoot = detectWorkspaceRoot();
  if (workspaceRoot) {
    await loadPackageGraph();
  }

  const config = vscode.workspace.getConfiguration("reasonscript");
  if (config.get<boolean>("autoCheck", true)) {
    vscode.commands.executeCommand("reasonscript.check");
  }
  console.log("[ReasonScript] activate complete");
}

export async function deactivate(): Promise<void> {
  await stopLanguageServer();
}
