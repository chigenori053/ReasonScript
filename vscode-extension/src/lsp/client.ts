import * as path from "path";
import * as vscode from "vscode";
import {
  CloseAction,
  ErrorAction,
  LanguageClient,
  LanguageClientOptions,
  Message,
  ServerOptions
} from "vscode-languageclient/node";

import { detectWorkspaceRoot, reasonExecutable, resolveReasonExecutable } from "../workspace/workspace";

export function createLanguageClient(context: vscode.ExtensionContext): LanguageClient {
  const workspaceRoot = detectWorkspaceRoot();
  const resolved = resolveReasonExecutable();

  // Determine working directory: prefer workspace root, then document dir, then extension path
  let cwd = workspaceRoot?.fsPath;
  if (!cwd) {
    const document = vscode.workspace.textDocuments.find(
      (candidate) => candidate.languageId === "reasonscript" && candidate.uri.scheme === "file"
    ) ?? vscode.window.activeTextEditor?.document;
    if (document?.uri.scheme === "file") {
      cwd = path.dirname(document.uri.fsPath);
    } else {
      cwd = context.extensionPath;
    }
  }

  // Launch the language server via reasonExecutable() (args: ["lsp"] with --stdio)
  const serverOptions: ServerOptions = {
    command: reasonExecutable(),
    args: ["lsp", "--stdio"],
    options: {
      cwd
    }
  };

  const clientOptions: LanguageClientOptions = {
    documentSelector: [
      { scheme: "file", language: "reasonscript", pattern: "**/*.rsn" }
    ],
    synchronize: {
      fileEvents: vscode.workspace.createFileSystemWatcher("**/*.{rsn,toml}")
    },
    workspaceFolder: workspaceRoot
      ? {
          uri: workspaceRoot,
          name: path.basename(workspaceRoot.fsPath),
          index: 0
        }
      : undefined,
    errorHandler: {
      error: (_error: Error, _message: Message | undefined, count: number | undefined) => {
        if (count && count <= 3) {
          return { action: ErrorAction.Continue };
        }
        return { action: ErrorAction.Shutdown };
      },
      closed: () => {
        vscode.window
          .showErrorMessage(
            "ReasonScript Language Server stopped unexpectedly.",
            "Restart Server",
            "Open Settings"
          )
          .then((selection) => {
            if (selection === "Restart Server") {
              vscode.commands.executeCommand("reasonscript.restartServer");
            } else if (selection === "Open Settings") {
              vscode.commands.executeCommand("workbench.action.openSettings", "reasonscript");
            }
          });
        return { action: CloseAction.DoNotRestart, handled: true };
      }
    }
  };

  return new LanguageClient(
    "reasonscriptLanguageServer",
    "ReasonScript Language Server",
    serverOptions,
    clientOptions
  );
}
