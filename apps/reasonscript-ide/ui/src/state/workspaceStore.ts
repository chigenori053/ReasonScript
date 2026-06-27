import { useState, useCallback } from "react";
import type { WorkspaceState } from "../types";

export interface WorkspaceStore {
  workspace: WorkspaceState | null;
  selectedPath: string | null;
  activeFilePath: string | null;
  expandedPaths: Set<string>;
  setWorkspace: (ws: WorkspaceState | null) => void;
  setSelectedPath: (path: string | null) => void;
  setActiveFilePath: (path: string | null) => void;
  toggleExpanded: (path: string) => void;
  clearWorkspace: () => void;
}

export function useWorkspaceStore(): WorkspaceStore {
  const [workspace, setWorkspaceRaw] = useState<WorkspaceState | null>(null);
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [activeFilePath, setActiveFilePath] = useState<string | null>(null);
  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(new Set());

  const setWorkspace = useCallback((ws: WorkspaceState | null) => {
    setWorkspaceRaw(ws);
  }, []);

  const toggleExpanded = useCallback((path: string) => {
    setExpandedPaths((prev) => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  }, []);

  const clearWorkspace = useCallback(() => {
    setWorkspaceRaw(null);
    setSelectedPath(null);
    setActiveFilePath(null);
    setExpandedPaths(new Set());
  }, []);

  return {
    workspace,
    selectedPath,
    activeFilePath,
    expandedPaths,
    setWorkspace,
    setSelectedPath,
    setActiveFilePath,
    toggleExpanded,
    clearWorkspace,
  };
}
