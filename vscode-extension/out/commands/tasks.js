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
exports.registerTaskProvider = registerTaskProvider;
const vscode = __importStar(require("vscode"));
const workspace_1 = require("../workspace/workspace");
function registerTaskProvider(context) {
    const provider = {
        provideTasks() {
            return ["build", "run", "test", "check"].map((command) => createTask({ type: "reasonscript", command }));
        },
        resolveTask(task) {
            const definition = task.definition;
            return createTask(definition);
        }
    };
    context.subscriptions.push(vscode.tasks.registerTaskProvider("reasonscript", provider));
}
function createTask(definition) {
    const args = [definition.command];
    if (definition.package) {
        args.push("--package", definition.package);
    }
    const task = new vscode.Task(definition, vscode.TaskScope.Workspace, `reason ${args.join(" ")}`, "ReasonScript", new vscode.ShellExecution((0, workspace_1.reasonExecutable)(), args));
    task.group = definition.command === "build" ? vscode.TaskGroup.Build : vscode.TaskGroup.Test;
    return task;
}
//# sourceMappingURL=tasks.js.map