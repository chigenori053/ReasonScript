import type { ProjectState } from "../types";
import { hashSource } from "./editorWorkspaceState";

export type ArtifactFreshnessStatus = "fresh" | "stale" | "unavailable" | "unknown";

export interface ArtifactFreshness {
  artifactName: string;
  status: ArtifactFreshnessStatus;
  sourceHash?: string;
  artifactSourceHash?: string;
  generatedAt?: string;
  reason?: string;
}

export interface ArtifactFreshnessViewModel {
  currentSourceHash: string;
  items: ArtifactFreshness[];
  overallStatus: ArtifactFreshnessStatus;
}

const TRACKED_ARTIFACTS: Array<{ name: string; key: keyof ProjectState }> = [
  { name: "surface_ast", key: "surface_ast" },
  { name: "reason_ir", key: "reason_ir" },
  { name: "execution_plan", key: "execution_plan" },
  { name: "simulation", key: "simulation" },
  { name: "knowledge", key: "knowledge" },
];

function artifactSourceOf(projectState: ProjectState): string | undefined {
  return projectState.source_files?.[0]?.text;
}

function freshnessFor(
  name: string,
  artifact: unknown,
  currentSourceHash: string,
  artifactSourceHash: string | undefined,
  generatedAt?: string
): ArtifactFreshness {
  if (artifact == null) {
    return { artifactName: name, status: "unavailable", generatedAt };
  }
  if (!artifactSourceHash) {
    return { artifactName: name, status: "unknown", generatedAt, reason: "No source snapshot recorded for this artifact." };
  }
  if (artifactSourceHash !== currentSourceHash) {
    return {
      artifactName: name,
      status: "stale",
      sourceHash: currentSourceHash,
      artifactSourceHash,
      generatedAt,
      reason: "Source has changed since this artifact was generated.",
    };
  }
  return {
    artifactName: name,
    status: "fresh",
    sourceHash: currentSourceHash,
    artifactSourceHash,
    generatedAt,
  };
}

export function buildArtifactFreshness(
  projectState: ProjectState | null,
  currentSource: string
): ArtifactFreshnessViewModel {
  const currentSourceHash = hashSource(currentSource);
  if (!projectState) {
    return {
      currentSourceHash,
      items: TRACKED_ARTIFACTS.map(({ name }) => ({ artifactName: name, status: "unavailable" })),
      overallStatus: "unavailable",
    };
  }

  const artifactSourceText = artifactSourceOf(projectState);
  const artifactSourceHash = artifactSourceText != null ? hashSource(artifactSourceText) : undefined;
  const generatedAt = projectState.generated_at;

  const items = TRACKED_ARTIFACTS.map(({ name, key }) =>
    freshnessFor(name, projectState[key], currentSourceHash, artifactSourceHash, generatedAt)
  );

  const overallStatus: ArtifactFreshnessStatus = items.some((item) => item.status === "stale")
    ? "stale"
    : items.every((item) => item.status === "unavailable")
      ? "unavailable"
      : "fresh";

  return { currentSourceHash, items, overallStatus };
}
