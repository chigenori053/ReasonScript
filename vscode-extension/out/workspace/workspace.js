"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.detectWorkspaceRoot = detectWorkspaceRoot;
exports.commandCwd = commandCwd;
exports.isProjectWorkspace = isProjectWorkspace;
exports.findOnPath = findOnPath;
exports.resolveReasonExecutable = resolveReasonExecutable;
exports.reasonExecutable = reasonExecutable;
const fs = __importStar(require("fs"));
const path = __importStar(require("path"));
const vscode = __importStar(require("vscode"));
function detectWorkspaceRoot(start) {
    const folders = vscode.workspace.workspaceFolders ?? [];
    const initial = start?.fsPath ?? folders[0]?.uri.fsPath;
    if (!initial) {
        return undefined;
    }
    let current = fs.statSync(initial).isDirectory() ? initial : path.dirname(initial);
    let packageRoot;
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
function commandCwd() {
    return detectWorkspaceRoot()?.fsPath;
}
function isProjectWorkspace() {
    const root = detectWorkspaceRoot();
    return Boolean(root && (fs.existsSync(path.join(root.fsPath, "reason.toml")) ||
        fs.existsSync(path.join(root.fsPath, "reason.workspace.toml"))));
}
function findOnPath(binaryName) {
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
            }
            catch {
                // Ignore file access errors on PATH entries
            }
        }
    }
    return undefined;
}
function resolveReasonExecutable() {
    // 1. VSCode 設定で明示指定されている場合はそれを優先
    const config = vscode.workspace.getConfiguration("reasonscript");
    const configured = config.get("executablePath", "").trim();
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
    const document = vscode.workspace.textDocuments.find((candidate) => candidate.languageId === "reasonscript" && candidate.uri.scheme === "file") ?? vscode.window.activeTextEditor?.document;
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
function reasonExecutable() {
    return resolveReasonExecutable().path;
}
//# sourceMappingURL=workspace.js.map