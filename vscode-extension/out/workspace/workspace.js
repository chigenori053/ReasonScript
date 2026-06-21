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
function reasonExecutable() {
    // 1. VSCode 設定で明示指定されている場合はそれを優先
    const config = vscode.workspace.getConfiguration("reasonscript");
    const configured = config.get("executablePath", "").trim();
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
//# sourceMappingURL=workspace.js.map