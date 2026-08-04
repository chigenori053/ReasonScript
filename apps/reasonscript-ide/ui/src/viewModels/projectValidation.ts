import type { PlatformDiagnostic, WorkspaceState } from "../types";
import type { WorkspaceDiagnosticsViewModel } from "./workspaceDiagnostics";
import type { ArtifactFreshnessStatus, ArtifactFreshnessViewModel } from "./artifactFreshness";

export type ProjectValidationStatus = "valid" | "warning" | "invalid" | "unavailable";

export interface ProjectValidationSummary {
  status: ProjectValidationStatus;
  workspaceRoot?: string;
  validFileCount: number;
  invalidFileCount: number;
  ignoredFileCount: number;
  diagnosticCount: number;
  errorCount: number;
  warningCount: number;
  artifactFreshness?: ArtifactFreshnessStatus;
  canAnalyze: boolean;
  canRun: boolean;
  reason?: string;
}

export function buildProjectValidationSummary(
  workspace: WorkspaceState | null,
  workspaceDiagnosticsVm: WorkspaceDiagnosticsViewModel,
  allDiagnostics: PlatformDiagnostic[],
  artifactFreshnessVm: ArtifactFreshnessViewModel
): ProjectValidationSummary {
  const errorCount = allDiagnostics.filter((d) => d.severity === "error").length;
  const warningCount = allDiagnostics.filter((d) => d.severity === "warning").length;

  if (!workspace) {
    return {
      status: "unavailable",
      validFileCount: 0,
      invalidFileCount: 0,
      ignoredFileCount: 0,
      diagnosticCount: allDiagnostics.length,
      errorCount,
      warningCount,
      canAnalyze: true,
      canRun: errorCount === 0,
      reason: "No workspace is open; validation applies to the current editor source only.",
    };
  }

  const status: ProjectValidationStatus =
    workspaceDiagnosticsVm.scanStatus === "failed" || errorCount > 0
      ? "invalid"
      : warningCount > 0 || workspaceDiagnosticsVm.scanTruncated || workspaceDiagnosticsVm.invalidFileCount > 0
        ? "warning"
        : "valid";

  return {
    status,
    workspaceRoot: workspace.root_path,
    validFileCount: workspaceDiagnosticsVm.validFileCount,
    invalidFileCount: workspaceDiagnosticsVm.invalidFileCount,
    ignoredFileCount: workspaceDiagnosticsVm.ignoredPaths.length,
    diagnosticCount: allDiagnostics.length,
    errorCount,
    warningCount,
    artifactFreshness: artifactFreshnessVm.overallStatus,
    canAnalyze: workspaceDiagnosticsVm.scanStatus !== "failed",
    canRun: status !== "invalid",
  };
}

export function projectValidationStatusLabel(status: ProjectValidationStatus): string {
  switch (status) {
    case "valid":
      return "Valid";
    case "warning":
      return "Warnings present";
    case "invalid":
      return "Invalid";
    default:
      return "Unavailable";
  }
}
