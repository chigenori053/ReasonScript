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
exports.activate = activate;
exports.deactivate = deactivate;
const vscode = __importStar(require("vscode"));
const toolchain_1 = require("./commands/toolchain");
const tasks_1 = require("./commands/tasks");
const client_1 = require("./lsp/client");
const packageGraph_1 = require("./workspace/packageGraph");
const workspace_1 = require("./workspace/workspace");
let client;
async function activate(context) {
    console.log("[ReasonScript] activate start");
    const statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
    statusBar.text = "ReasonScript Ready";
    statusBar.show();
    context.subscriptions.push(statusBar);
    const outputChannel = vscode.window.createOutputChannel("ReasonScript");
    context.subscriptions.push(outputChannel);
    (0, toolchain_1.registerToolchainCommands)(context, statusBar);
    (0, tasks_1.registerTaskProvider)(context);
    console.log("[ReasonScript] commands registered");
    outputChannel.appendLine("Starting language server...");
    try {
        console.log("[ReasonScript] lsp startup");
        client = (0, client_1.createLanguageClient)(context);
        context.subscriptions.push(client);
        await client.start();
        statusBar.text = "ReasonScript LSP Online";
        outputChannel.appendLine("Language server started.");
    }
    catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        statusBar.text = "ReasonScript LSP Offline";
        outputChannel.appendLine(`Language server unavailable:\n${msg}`);
        outputChannel.appendLine("Toolchain commands remain available.");
        vscode.window.showWarningMessage(`ReasonScript: Language server unavailable. ${msg}`);
    }
    const workspaceRoot = (0, workspace_1.detectWorkspaceRoot)();
    if (workspaceRoot) {
        await (0, packageGraph_1.loadPackageGraph)();
    }
    const config = vscode.workspace.getConfiguration("reasonscript");
    if (config.get("autoCheck", true)) {
        vscode.commands.executeCommand("reasonscript.check");
    }
    console.log("[ReasonScript] activate complete");
}
async function deactivate() {
    if (client) {
        await client.stop();
        client = undefined;
    }
}
//# sourceMappingURL=extension.js.map