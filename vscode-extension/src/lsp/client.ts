import * as path from "path";
import * as vscode from "vscode";
import {
  LanguageClient,
  LanguageClientOptions,
  ServerOptions,
  TransportKind
} from "vscode-languageclient/node";

import { detectWorkspaceRoot, reasonExecutable } from "../workspace/workspace";

export function createLanguageClient(context: vscode.ExtensionContext): LanguageClient {
  const workspaceRoot = detectWorkspaceRoot();
  const serverOptions: ServerOptions = {
    // Use the public CLI instead of importing a checkout-local Python module.
    // This works for both a source checkout and an installed ReasonScript
    // distribution, where the extension cannot rely on PYTHONPATH.
    command: reasonExecutable(),
    args: ["lsp"],
    transport: TransportKind.stdio,
    options: {
      cwd: workspaceRoot?.fsPath ?? context.extensionPath
    }
  };
  const clientOptions: LanguageClientOptions = {
    documentSelector: [{ scheme: "file", language: "reasonscript" }],
    synchronize: {
      fileEvents: vscode.workspace.createFileSystemWatcher("**/*.{rsn,toml}")
    },
    workspaceFolder: workspaceRoot
      ? {
          uri: workspaceRoot,
          name: path.basename(workspaceRoot.fsPath),
          index: 0
        }
      : undefined
  };
  return new LanguageClient(
    "reasonscriptLanguageServer",
    "ReasonScript Language Server",
    serverOptions,
    clientOptions
  );
}
