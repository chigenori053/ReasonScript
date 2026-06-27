import { invoke } from "@tauri-apps/api/core";
import type { FileNode, ProjectState, WorkspaceState } from "./types";

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

export async function openWorkspace(path: string): Promise<WorkspaceState> {
  return await invoke<WorkspaceState>("open_workspace", { path });
}

export async function listWorkspaceFiles(rootPath: string): Promise<FileNode[]> {
  return await invoke<FileNode[]>("list_workspace_files", { rootPath });
}

export async function refreshWorkspace(rootPath: string): Promise<WorkspaceState> {
  return await invoke<WorkspaceState>("refresh_workspace", { rootPath });
}

export async function selectWorkspaceFile(
  rootPath: string,
  relativePath: string
): Promise<FileNode> {
  return await invoke<FileNode>("select_workspace_file", {
    rootPath,
    relativePath,
  });
}
