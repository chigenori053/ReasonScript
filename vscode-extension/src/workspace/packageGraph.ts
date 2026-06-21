import * as childProcess from "child_process";
import { commandCwd } from "./workspace";

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
  const script = [
    "import json",
    "from toolchain.workspace import load_package_graph",
    "print(json.dumps(load_package_graph('.').to_dict()))"
  ].join("; ");
  return new Promise((resolve) => {
    childProcess.execFile("python3", ["-c", script], { cwd }, (error, stdout) => {
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
