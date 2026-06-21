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

  // 3. PATH フォールバック（システムにインストール済みの場合）
  return process.platform === "win32" ? "reason.bat" : "reason";
}
