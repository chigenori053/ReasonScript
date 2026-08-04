import type { WorkspaceState } from "../types";

export type EditorSourceKind = "workspace_file" | "sample" | "unsaved" | "missing";

export interface EditorWorkspaceState {
  sourceKind: EditorSourceKind;
  relativePath?: string;
  sampleId?: string;
  dirty: boolean;
  sourceHash?: string;
  selectedFileExists: boolean;
  lastSavedHash?: string;
}

export interface EditorWorkspaceStateInput {
  selectedPath: string | null;
  activeFilePath: string | null;
  sampleId?: string | null;
  source: string;
  savedSource: string;
  workspace: WorkspaceState | null;
}

// Small deterministic string hash (FNV-1a), sufficient for freshness comparisons.
export function hashSource(text: string): string {
  let hash = 0x811c9dc5;
  for (let i = 0; i < text.length; i += 1) {
    hash ^= text.charCodeAt(i);
    hash = Math.imul(hash, 0x01000193);
  }
  return (hash >>> 0).toString(16);
}

function findNode(
  nodes: WorkspaceState["files"],
  relativePath: string
): boolean {
  for (const node of nodes) {
    if (node.kind === "directory") {
      if (findNode(node.children, relativePath)) return true;
      continue;
    }
    if (node.relative_path === relativePath) return true;
  }
  return false;
}

export function deriveEditorWorkspaceState(input: EditorWorkspaceStateInput): EditorWorkspaceState {
  const { selectedPath, activeFilePath, sampleId, source, savedSource, workspace } = input;
  const dirty = source !== savedSource;
  const sourceHash = hashSource(source);
  const lastSavedHash = hashSource(savedSource);
  const relativePath = selectedPath ?? activeFilePath ?? undefined;

  if (relativePath && workspace) {
    const selectedFileExists = findNode(workspace.files, relativePath);
    if (!selectedFileExists) {
      return {
        sourceKind: "missing",
        relativePath,
        dirty,
        sourceHash,
        lastSavedHash,
        selectedFileExists: false,
      };
    }
    return {
      sourceKind: "workspace_file",
      relativePath,
      dirty,
      sourceHash,
      lastSavedHash,
      selectedFileExists: true,
    };
  }

  if (sampleId) {
    return {
      sourceKind: "sample",
      sampleId,
      dirty,
      sourceHash,
      lastSavedHash,
      selectedFileExists: true,
    };
  }

  return {
    sourceKind: "unsaved",
    dirty,
    sourceHash,
    lastSavedHash,
    selectedFileExists: true,
  };
}

export function editorSourceKindLabel(kind: EditorSourceKind): string {
  switch (kind) {
    case "workspace_file":
      return "Workspace file";
    case "sample":
      return "Sample source";
    case "unsaved":
      return "Unsaved source";
    case "missing":
      return "File missing";
    default:
      return "Unknown";
  }
}
