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
exports.createLanguageClient = createLanguageClient;
const path = __importStar(require("path"));
const vscode = __importStar(require("vscode"));
const node_1 = require("vscode-languageclient/node");
const workspace_1 = require("../workspace/workspace");
function createLanguageClient(context) {
    const workspaceRoot = (0, workspace_1.detectWorkspaceRoot)();
    const resolved = (0, workspace_1.resolveReasonExecutable)();
    // Determine working directory: prefer workspace root, then document dir, then extension path
    let cwd = workspaceRoot?.fsPath;
    if (!cwd) {
        const document = vscode.workspace.textDocuments.find((candidate) => candidate.languageId === "reasonscript" && candidate.uri.scheme === "file") ?? vscode.window.activeTextEditor?.document;
        if (document?.uri.scheme === "file") {
            cwd = path.dirname(document.uri.fsPath);
        }
        else {
            cwd = context.extensionPath;
        }
    }
    // Launch the language server via reasonExecutable() (args: ["lsp"] with --stdio)
    const serverOptions = {
        command: (0, workspace_1.reasonExecutable)(),
        args: ["lsp", "--stdio"],
        options: {
            cwd
        }
    };
    const clientOptions = {
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
            error: (_error, _message, count) => {
                if (count && count <= 3) {
                    return { action: node_1.ErrorAction.Continue };
                }
                return { action: node_1.ErrorAction.Shutdown };
            },
            closed: () => {
                vscode.window
                    .showErrorMessage("ReasonScript Language Server stopped unexpectedly.", "Restart Server", "Open Settings")
                    .then((selection) => {
                    if (selection === "Restart Server") {
                        vscode.commands.executeCommand("reasonscript.restartServer");
                    }
                    else if (selection === "Open Settings") {
                        vscode.commands.executeCommand("workbench.action.openSettings", "reasonscript");
                    }
                });
                return { action: node_1.CloseAction.DoNotRestart, handled: true };
            }
        }
    };
    return new node_1.LanguageClient("reasonscriptLanguageServer", "ReasonScript Language Server", serverOptions, clientOptions);
}
//# sourceMappingURL=client.js.map