import { invoke } from "@tauri-apps/api/core";
import type { FileNode, ProjectState, WorkspaceState } from "./types";

export interface AnalyzeSourceContext {
  workspace_root: string;
  relative_path: string;
  dirty: boolean;
}

export async function buildProjectState(
  source: string,
  uri: string = "file:///main.rsn",
  sourceContext?: AnalyzeSourceContext
): Promise<ProjectState> {
  const filename = sourceContext?.relative_path ?? uri.replace(/^file:\/\//, "") ?? "playground.rsn";
  const response = await fetch("/api/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      source,
      filename,
      compiler_mode: "normal",
      ...(sourceContext ? { source_context: sourceContext } : {}),
    }),
  });

  if (!response.ok) {
    throw new Error(`Analyze request failed with status ${response.status}`);
  }

  const data = (await response.json()) as Record<string, unknown>;
  return {
    schema_version: String(data.schema_version ?? "reasonscript-project-state/0.1"),
    compiler_version: String(data.compiler_version ?? "playground-backend"),
    workspace: {
      root_uri: sourceContext?.workspace_root,
      project_name: sourceContext?.workspace_root?.split("/").filter(Boolean).pop(),
    },
    source_files: [
      {
        uri,
        text: source,
        language_id: "reasonscript",
      },
    ],
    surface_ast: data.surface_ast ?? data.ast ?? null,
    semantic_ast: data.semantic_ast ?? null,
    reason_ir: data.reason_ir ?? (Array.isArray(data.reason_irs) ? data.reason_irs[0] : null) ?? null,
    execution_plan: data.execution_plan ?? null,
    diagnostics: Array.isArray(data.diagnostics) ? data.diagnostics as ProjectState["diagnostics"] : [],
    validation: data.validation ?? null,
    analyzer: data.analysis ?? data.analyzer ?? null,
    runtime_operations: data.runtime_operations ?? null,
    simulation: data.simulation ?? null,
    knowledge: data.knowledge ?? null,
    metadata: {
      compiler_mode: String(data.compiler_mode ?? "normal"),
      source_filename: filename,
    },
    generated_at: String(data.generated_at ?? new Date().toISOString()),
  };
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
