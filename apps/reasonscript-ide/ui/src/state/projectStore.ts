import { useState, useCallback } from "react";
import type { ProjectState, PlatformDiagnostic, ArtifactSelection } from "../types";

export type BuildStatus = "idle" | "building" | "ok" | "error";

export interface ProjectStore {
  projectState: ProjectState | null;
  buildStatus: BuildStatus;
  lastError: string | null;
  selectedArtifact: ArtifactSelection | null;
  hoveredArtifact: ArtifactSelection | null;
  setProjectState: (state: ProjectState) => void;
  setBuildStatus: (s: BuildStatus) => void;
  setLastError: (e: string | null) => void;
  clearState: () => void;
  setSelectedArtifact: (sel: ArtifactSelection | null) => void;
  setHoveredArtifact: (sel: ArtifactSelection | null) => void;
  diagnostics: PlatformDiagnostic[];
}

export function useProjectStore(): ProjectStore {
  const [projectState, setProjectStateRaw] = useState<ProjectState | null>(null);
  const [buildStatus, setBuildStatus] = useState<BuildStatus>("idle");
  const [lastError, setLastError] = useState<string | null>(null);
  const [selectedArtifact, setSelectedArtifact] = useState<ArtifactSelection | null>(null);
  const [hoveredArtifact, setHoveredArtifact] = useState<ArtifactSelection | null>(null);

  const setProjectState = useCallback((state: ProjectState) => {
    setProjectStateRaw(state);
    const hasErrors = state.diagnostics.some((d) => d.severity === "error");
    setBuildStatus(hasErrors ? "error" : "ok");
    setLastError(null);
  }, []);

  const clearState = useCallback(() => {
    setProjectStateRaw(null);
    setBuildStatus("idle");
    setLastError(null);
    setSelectedArtifact(null);
    setHoveredArtifact(null);
  }, []);

  return {
    projectState,
    buildStatus,
    lastError,
    selectedArtifact,
    hoveredArtifact,
    setProjectState,
    setBuildStatus,
    setLastError,
    clearState,
    setSelectedArtifact,
    setHoveredArtifact,
    diagnostics: projectState?.diagnostics ?? [],
  };
}
