import * as childProcess from "child_process";
import * as vscode from "vscode";

import { commandCwd, reasonExecutable } from "../workspace/workspace";

export type ToolchainCommand = "build" | "run" | "test" | "check";

console.log("[ReasonScript] toolchain module loaded");

let _outputChannels: Record<ToolchainCommand, vscode.OutputChannel> | undefined;

export function getOutputChannels(): Record<ToolchainCommand, vscode.OutputChannel> {
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

export function registerToolchainCommands(
  context: vscode.ExtensionContext,
  statusBar: vscode.StatusBarItem
): void {
  for (const command of ["build", "run", "test", "check"] as ToolchainCommand[]) {
    context.subscriptions.push(
      vscode.commands.registerCommand(`reasonscript.${command}`, async (packageName?: string) => {
        await runToolchain(command, statusBar, packageName);
      })
    );
  }
}

export function runToolchain(
  command: ToolchainCommand,
  statusBar: vscode.StatusBarItem,
  packageName?: string
): Promise<number> {
  const cwd = commandCwd();
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
  const args: string[] = [command];
  if (packageName) {
    args.push("--package", packageName);
  }
  channel.appendLine(`$ ${reasonExecutable()} ${args.join(" ")}`);
  return new Promise((resolve) => {
    const child = childProcess.spawn(reasonExecutable(), args, { cwd, shell: process.platform === "win32" });
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

function updateStatus(command: ToolchainCommand, exitCode: number, statusBar: vscode.StatusBarItem): void {
  if (command === "build") {
    statusBar.text = exitCode === 0 ? "ReasonScript: Build Success" : "ReasonScript: Build Failed";
  } else if (command === "test") {
    statusBar.text = exitCode === 0 ? "ReasonScript: Tests Passed" : "ReasonScript: Tests Failed";
  } else {
    statusBar.text = exitCode === 0 ? "ReasonScript Ready" : `ReasonScript: ${command} failed`;
  }
  statusBar.show();
}
