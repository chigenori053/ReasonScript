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
exports.getOutputChannels = getOutputChannels;
exports.registerToolchainCommands = registerToolchainCommands;
exports.runToolchain = runToolchain;
const childProcess = __importStar(require("child_process"));
const vscode = __importStar(require("vscode"));
const workspace_1 = require("../workspace/workspace");
console.log("[ReasonScript] toolchain module loaded");
let _outputChannels;
function getOutputChannels() {
    if (!_outputChannels) {
        _outputChannels = {
            build: vscode.window.createOutputChannel("ReasonScript Build"),
            run: vscode.window.createOutputChannel("ReasonScript Run"),
            test: vscode.window.createOutputChannel("ReasonScript Test"),
            check: vscode.window.createOutputChannel("ReasonScript Check")
        };
    }
    return _outputChannels;
}
function registerToolchainCommands(context, statusBar) {
    for (const command of ["build", "run", "test", "check"]) {
        context.subscriptions.push(vscode.commands.registerCommand(`reasonscript.${command}`, async (packageName) => {
            await runToolchain(command, statusBar, packageName);
        }));
    }
}
function runToolchain(command, statusBar, packageName) {
    const cwd = (0, workspace_1.commandCwd)();
    const channel = getOutputChannels()[command];
    channel.clear();
    channel.show(true);
    if (!cwd) {
        channel.appendLine("Error:");
        channel.appendLine("");
        channel.appendLine("WorkspaceNotFound");
        updateStatus(command, 1, statusBar);
        return Promise.resolve(1);
    }
    const args = [command];
    if (packageName) {
        args.push("--package", packageName);
    }
    channel.appendLine(`$ ${(0, workspace_1.reasonExecutable)()} ${args.join(" ")}`);
    return new Promise((resolve) => {
        const child = childProcess.spawn((0, workspace_1.reasonExecutable)(), args, { cwd, shell: process.platform === "win32" });
        child.stdout.on("data", (data) => channel.append(data.toString()));
        child.stderr.on("data", (data) => channel.append(data.toString()));
        child.on("error", (error) => {
            channel.appendLine(`Error:\n\nToolchainLaunchFailed\n\n${error.message}`);
            updateStatus(command, 1, statusBar);
            resolve(1);
        });
        child.on("close", (code) => {
            const exitCode = code ?? 1;
            updateStatus(command, exitCode, statusBar);
            resolve(exitCode);
        });
    });
}
function updateStatus(command, exitCode, statusBar) {
    if (command === "build") {
        statusBar.text = exitCode === 0 ? "ReasonScript: Build Success" : "ReasonScript: Build Failed";
    }
    else if (command === "test") {
        statusBar.text = exitCode === 0 ? "ReasonScript: Tests Passed" : "ReasonScript: Tests Failed";
    }
    else {
        statusBar.text = exitCode === 0 ? "ReasonScript Ready" : `ReasonScript: ${command} failed`;
    }
    statusBar.show();
}
//# sourceMappingURL=toolchain.js.map