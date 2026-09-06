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

export interface ResolvedExecutable {
  path: string;
  exists: boolean;
  source: "config" | "workspace" | "document" | "path";
}

export function findOnPath(binaryName: string): string | undefined {
  const envPath = process.env.PATH ?? "";
  const extensions = process.platform === "win32" ? [".exe", ".bat", ".cmd", ""] : [""];
  for (const dir of envPath.split(path.delimiter)) {
    if (!dir) {
      continue;
    }
    for (const ext of extensions) {
      const fullPath = path.join(dir, binaryName + ext);
      try {
        if (fs.existsSync(fullPath) && fs.statSync(fullPath).isFile()) {
          return fullPath;
        }
      } catch {
        // Ignore file access errors on PATH entries
      }
    }
  }
  return undefined;
}

export function resolveReasonExecutable(): ResolvedExecutable {
  // 1. VSCode 設定で明示指定されている場合はそれを優先
  const config = vscode.workspace.getConfiguration("reasonscript");
  const configured = config.get<string>("executablePath", "").trim();
  if (configured) {
    const exists = fs.existsSync(configured);
    return { path: configured, exists, source: "config" };
  }

  // 2. ワークスペースルートまたはその親にある `reason` スクリプトを探す
  const root = detectWorkspaceRoot();
  if (root) {
    const candidateParent = path.join(root.fsPath, "..", "reason");
    if (fs.existsSync(candidateParent)) {
      return { path: candidateParent, exists: true, source: "workspace" };
    }
    const candidateInRoot = path.join(root.fsPath, "reason");
    if (fs.existsSync(candidateInRoot)) {
      return { path: candidateInRoot, exists: true, source: "workspace" };
    }
  }

  // 3. 単一 .rsn ファイルのアクティブドキュメント親階層から探索
  const document = vscode.workspace.textDocuments.find(
    (candidate) => candidate.languageId === "reasonscript" && candidate.uri.scheme === "file"
  ) ?? vscode.window.activeTextEditor?.document;
  if (document?.uri.scheme === "file") {
    let current = path.dirname(document.uri.fsPath);
    while (true) {
      const candidate = path.join(current, "reason");
      if (fs.existsSync(candidate)) {
        return { path: candidate, exists: true, source: "document" };
      }
      const parent = path.dirname(current);
      if (parent === current) {
        break;
      }
      current = parent;
    }
  }

  // 4. PATH フォールバック
  const defaultBinary = process.platform === "win32" ? "reason.bat" : "reason";
  const pathLocation = findOnPath(defaultBinary);
  if (pathLocation) {
    return { path: pathLocation, exists: true, source: "path" };
  }

  return { path: defaultBinary, exists: false, source: "path" };
}

export function reasonExecutable(): string {
  return resolveReasonExecutable().path;
}
