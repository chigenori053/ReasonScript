import * as vscode from "vscode";
import { reasonExecutable } from "../workspace/workspace";

type ReasonScriptTaskDefinition = vscode.TaskDefinition & {
  command: "build" | "run" | "test" | "check";
  package?: string;
};

export function registerTaskProvider(context: vscode.ExtensionContext): void {
  const provider: vscode.TaskProvider = {
    provideTasks(): vscode.ProviderResult<vscode.Task[]> {
      return ["build", "run", "test", "check"].map((command) => createTask({ type: "reasonscript", command } as ReasonScriptTaskDefinition));
    },
    resolveTask(task: vscode.Task): vscode.ProviderResult<vscode.Task> {
      const definition = task.definition as ReasonScriptTaskDefinition;
      return createTask(definition);
    }
  };
  context.subscriptions.push(vscode.tasks.registerTaskProvider("reasonscript", provider));
}

function createTask(definition: ReasonScriptTaskDefinition): vscode.Task {
  const args: string[] = [definition.command];
  if (definition.package) {
    args.push("--package", definition.package);
  }
  const task = new vscode.Task(
    definition,
    vscode.TaskScope.Workspace,
    `reason ${args.join(" ")}`,
    "ReasonScript",
    new vscode.ShellExecution(reasonExecutable(), args)
  );
  task.group = definition.command === "build" ? vscode.TaskGroup.Build : vscode.TaskGroup.Test;
  return task;
}
