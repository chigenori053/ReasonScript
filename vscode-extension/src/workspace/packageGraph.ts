import * as childProcess from "child_process";
import * as fs from "fs";
import * as path from "path";
import { commandCwd, resolveReasonExecutable } from "./workspace";

export interface PackageGraph {
  schema: string;
  packages: Array<{ name: string; version: string; path: string }>;
  dependencies: Array<{ package: string; dependency: string; requirement: string; kind: string }>;
  build_order: string[];
}

export function loadPackageGraph(): Promise<PackageGraph | undefined> {
  const cwd = commandCwd();
  if (!cwd) {
    return Promise.resolve(undefined);
  }
  const toolchainRoot = resolveToolchainRoot();
  if (!toolchainRoot) {
    return Promise.resolve(undefined);
  }
  // `-I` keeps the workspace (cwd) and PYTHON* variables off sys.path, so a
  // `toolchain/` package inside an opened repository is never imported.
  const script = [
    "import json, sys",
    "sys.path.insert(0, sys.argv[1])",
    "from toolchain.workspace import load_package_graph",
    "print(json.dumps(load_package_graph(sys.argv[2]).to_dict()))"
  ].join("; ");
  return new Promise((resolve) => {
    childProcess.execFile("python3", ["-I", "-c", script, toolchainRoot, cwd], { cwd }, (error, stdout) => {
      if (error) {
        resolve(undefined);
        return;
      }
      try {
        resolve(JSON.parse(stdout) as PackageGraph);
      } catch {
        resolve(undefined);
      }
    });
  });
}

function resolveToolchainRoot(): string | undefined {
  const resolved = resolveReasonExecutable();
  if (!resolved.exists) {
    return undefined;
  }
  try {
    const root = path.dirname(fs.realpathSync(resolved.path));
    return fs.existsSync(path.join(root, "toolchain", "workspace.py")) ? root : undefined;
  } catch {
    return undefined;
  }
}
