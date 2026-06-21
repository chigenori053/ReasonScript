import * as path from "path";
import * as vscode from "vscode";
import {
  LanguageClient,
  LanguageClientOptions,
  ServerOptions,
  TransportKind
} from "vscode-languageclient/node";

import { detectWorkspaceRoot } from "../workspace/workspace";

export function createLanguageClient(context: vscode.ExtensionContext): LanguageClient {
  const workspaceRoot = detectWorkspaceRoot();
  const serverModule = "frontend.lsp";
  const serverOptions: ServerOptions = {
    command: "python3",
    args: ["-m", serverModule],
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
