import * as vscode from "vscode";
import { LanguageClient } from "vscode-languageclient/node";

import { registerToolchainCommands } from "./commands/toolchain";
import { registerTaskProvider } from "./commands/tasks";
import { createLanguageClient } from "./lsp/client";
import { loadPackageGraph } from "./workspace/packageGraph";
import { detectWorkspaceRoot } from "./workspace/workspace";

let client: LanguageClient | undefined;

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
  console.log("[ReasonScript] commands registered");

  outputChannel.appendLine("Starting language server...");
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
    vscode.window.showWarningMessage(`ReasonScript: Language server unavailable. ${msg}`);
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
  if (client) {
    await client.stop();
    client = undefined;
  }
}
