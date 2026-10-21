import * as childProcess from "child_process";
import * as vscode from "vscode";

import { commandCwd, isProjectWorkspace, reasonExecutable } from "../workspace/workspace";

export type ToolchainCommand = "build" | "run" | "test" | "check";

// cmd.exe interprets these even inside double quotes (or ends the quoting).
const WINDOWS_SHELL_METACHARACTERS = /["%!^&|<>\r\n]/;

function quoteWindowsArgument(value: string): string {
  return /[\s()]/.test(value) ? `"${value}"` : value;
}

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
  if (command === "check" && !packageName && !isProjectWorkspace()) {
    const document = vscode.window.activeTextEditor?.document;
    if (document?.languageId === "reasonscript" && document.uri.scheme === "file") {
      args.push(document.uri.fsPath);
    }
  }
  const executable = reasonExecutable();
  const useShell = process.platform === "win32";
  const unsafe = useShell ? [executable, ...args].find((value) => WINDOWS_SHELL_METACHARACTERS.test(value)) : undefined;
  if (unsafe !== undefined) {
    channel.appendLine("Error:");
    channel.appendLine("");
    channel.appendLine(`UnsafeCommandArgument: ${unsafe}`);
    updateStatus(command, 1, statusBar);
    return Promise.resolve(1);
  }
  channel.appendLine(`$ ${executable} ${args.join(" ")}`);
  return new Promise((resolve) => {
    // On Windows the `reason` launcher is a .bat/.cmd file, which Node only
    // starts through cmd.exe; arguments are validated above and quoted here.
    const child = useShell
      ? childProcess.spawn(quoteWindowsArgument(executable), args.map(quoteWindowsArgument), { cwd, shell: true })
      : childProcess.spawn(executable, args, { cwd });
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
