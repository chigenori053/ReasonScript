import * as fs from "fs";
import * as path from "path";
import * as vscode from "vscode";

export function detectWorkspaceRoot(start?: vscode.Uri): vscode.Uri | undefined {
  const folders = vscode.workspace.workspaceFolders ?? [];
  const initial = start?.fsPath ?? folders[0]?.uri.fsPath;
  if (!initial) {
    return undefined;
  }
  let current = fs.statSync(initial).isDirectory() ? initial : path.dirname(initial);
  let packageRoot: string | undefined;
  while (true) {
    if (fs.existsSync(path.join(current, "reason.workspace.toml"))) {
      return vscode.Uri.file(current);
    }
    if (!packageRoot && fs.existsSync(path.join(current, "reason.toml"))) {
      packageRoot = current;
    }
    const parent = path.dirname(current);
    if (parent === current) {
      break;
    }
    current = parent;
  }
  return packageRoot ? vscode.Uri.file(packageRoot) : folders[0]?.uri;
}

export function commandCwd(): string | undefined {
  return detectWorkspaceRoot()?.fsPath;
}

export function isProjectWorkspace(): boolean {
  const root = detectWorkspaceRoot();
  return Boolean(
    root && (
      fs.existsSync(path.join(root.fsPath, "reason.toml")) ||
      fs.existsSync(path.join(root.fsPath, "reason.workspace.toml"))
    )
  );
}

export function reasonExecutable(): string {
  // 1. VSCode 設定で明示指定されている場合はそれを優先
  const config = vscode.workspace.getConfiguration("reasonscript");
  const configured = config.get<string>("executablePath", "").trim();
  if (configured) {
    return configured;
  }

  // 2. ワークスペースルートの隣にある `reason` スクリプトを探す
  //    例: /path/to/ReasonScript/reason
  const root = detectWorkspaceRoot();
  if (root) {
    const candidate = path.join(root.fsPath, "..", "reason");
    if (fs.existsSync(candidate)) {
      return candidate;
    }
    // ワークスペース自体のルートも確認
    const candidateInRoot = path.join(root.fsPath, "reason");
    if (fs.existsSync(candidateInRoot)) {
      return candidateInRoot;
    }
  }

  // A single .rsn file can activate the extension without opening its parent
  // folder as a VS Code workspace. In that case, find a checkout-local CLI
  // from the active document before falling back to PATH.
  const document = vscode.workspace.textDocuments.find(
    (candidate) => candidate.languageId === "reasonscript" && candidate.uri.scheme === "file"
  ) ?? vscode.window.activeTextEditor?.document;
  if (document?.uri.scheme === "file") {
    let current = path.dirname(document.uri.fsPath);
    while (true) {
      const candidate = path.join(current, "reason");
      if (fs.existsSync(candidate)) {
        return candidate;
      }
      const parent = path.dirname(current);
      if (parent === current) {
        break;
      }
      current = parent;
    }
  }

  // 3. PATH フォールバック（システムにインストール済みの場合）
  return process.platform === "win32" ? "reason.bat" : "reason";
}
