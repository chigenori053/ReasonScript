import { invoke } from "@tauri-apps/api/core";
import type { ProjectState } from "./types";

export async function buildProjectState(
  source: string,
  uri: string = "file:///main.rsn"
): Promise<ProjectState> {
  console.log("[bridge] buildProjectState via Tauri invoke", {
    uri,
    sourceLength: source.length,
  });

  return await invoke<ProjectState>("build_project_state", {
    source,
    uri,
  });
}

export async function openFile(path: string): Promise<string> {
  return await invoke<string>("open_file", { path });
}

export async function saveFile(path: string, content: string): Promise<void> {
  return await invoke<void>("save_file", { path, content });
}

export async function listProjectFiles(root: string): Promise<string[]> {
  return await invoke<string[]>("list_project_files", { root });
}

export async function exportProjectState(state: ProjectState, path: string): Promise<void> {
  return await invoke<void>("export_project_state", { state, path });
}
