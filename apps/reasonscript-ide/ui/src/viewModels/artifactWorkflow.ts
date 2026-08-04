import type { PlatformDiagnostic, ProjectState } from "../types";

export type ArtifactOperationKind =
  | "export"
  | "import"
  | "diff";

export type ArtifactOperationStatus =
  | "idle"
  | "running"
  | "success"
  | "failed"
  | "unavailable";

export type ArtifactIssueSeverity =
  | "error"
  | "warning"
  | "info";

export interface ArtifactIssue {
  id: string;
  operation: ArtifactOperationKind;
  severity: ArtifactIssueSeverity;
  code?: string;
  message: string;
  path?: string;
  evidence?: unknown;
}

export interface ArtifactOperationLog {
  id: string;
  operation: ArtifactOperationKind;
  message: string;
  status?: ArtifactOperationStatus;
  timestamp?: string;
  evidence?: unknown;
}

export interface ExportArtifactResult {
  status: ArtifactOperationStatus;
  artifactId?: string;
  artifactName?: string;
  artifactPath?: string;
  files?: string[];
  bundle?: unknown;
  raw?: unknown;
}

export interface ImportArtifactResult {
  status: ArtifactOperationStatus;
  importedFiles?: string[];
  restoredArtifacts?: string[];
  validationIssues: ArtifactIssue[];
  raw?: unknown;
}

export interface DiffArtifactResult {
  status: ArtifactOperationStatus;
  summary?: {
    changed?: number;
    added?: number;
    removed?: number;
    unchanged?: number;
  };
  issues: ArtifactIssue[];
  comparedArtifacts?: string[];
  raw?: unknown;
}

export interface ArtifactWorkflowViewModel {
  exportResult: ExportArtifactResult;
  importResult: ImportArtifactResult;
  diffResult: DiffArtifactResult;
  issues: ArtifactIssue[];
  logs: ArtifactOperationLog[];
  summary: {
    lastOperation?: ArtifactOperationKind;
    lastStatus?: ArtifactOperationStatus;
    issueCount: number;
    logCount: number;
  };
}

const idleExport: ExportArtifactResult = { status: "idle" };
const idleImport: ImportArtifactResult = { status: "idle", validationIssues: [] };
const idleDiff: DiffArtifactResult = { status: "idle", issues: [] };

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return isRecord(value) ? value : null;
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function asString(value: unknown): string | undefined {
  return typeof value === "string" && value.length > 0 ? value : undefined;
}

function asNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function asStatus(value: unknown, raw?: Record<string, unknown> | null): ArtifactOperationStatus {
  const status = String(value ?? "").toLowerCase();
  if (["idle", "running", "success", "failed", "unavailable"].includes(status)) {
    return status as ArtifactOperationStatus;
  }
  if (raw && raw.ok === false) return "failed";
  if (raw && raw.ok === true) return "success";
  return raw ? "success" : "idle";
}

function statusFromOperation(value: unknown): ArtifactOperationStatus {
  const record = asRecord(value);
  return asStatus(record?.status, record);
}

function issueSeverity(value: unknown): ArtifactIssueSeverity {
  const raw = String(value ?? "").toLowerCase();
  if (raw.includes("error") || raw.includes("fail")) return "error";
  if (raw.includes("warn") || raw.includes("mismatch") || raw.includes("compat")) return "warning";
  return "info";
}

function issueMessage(record: Record<string, unknown>): string {
  return String(record.message ?? record.detail ?? record.reason ?? record.phase ?? "Artifact workflow issue");
}

function normalizeIssue(value: unknown, operation: ArtifactOperationKind, index: number): ArtifactIssue {
  const record = asRecord(value) ?? {};
  return {
    id: asString(record.id ?? record.issue_id) ?? `${operation}-issue-${index}`,
    operation,
    severity: issueSeverity(record.severity ?? record.level ?? record.status ?? record.phase),
    code: asString(record.code ?? record.phase),
    message: issueMessage(record),
    path: asString(record.path ?? record.file ?? record.filename),
    evidence: value,
  };
}

function collectIssues(raw: Record<string, unknown> | null, operation: ArtifactOperationKind): ArtifactIssue[] {
  if (!raw) return [];
  const candidates = [
    ...asArray(raw.validationIssues ?? raw.validation_issues),
    ...asArray(raw.compatibilityIssues ?? raw.compatibility_issues),
    ...asArray(raw.issues),
    ...asArray(raw.warnings),
    ...asArray(raw.errors),
  ];
  if (operation === "diff") {
    for (const change of asArray(raw.changes)) {
      const record = asRecord(change);
      if (record && record.status !== "changed") continue;
      candidates.push({
        severity: "warning",
        code: "DIFF_CHANGED",
        message: `Diff structural mismatch: ${String(record?.artifact ?? "artifact")}`,
        evidence: change,
      });
    }
  }
  return candidates.map((candidate, index) => normalizeIssue(candidate, operation, index));
}

function filesFrom(raw: Record<string, unknown> | null): string[] | undefined {
  const files = asArray(raw?.files).map(String);
  return files.length > 0 ? files : undefined;
}

function artifactPathFrom(raw: Record<string, unknown> | null): string | undefined {
  return asString(raw?.artifactPath ?? raw?.artifact_path ?? raw?.path);
}

function buildExportResult(rawValue: unknown): ExportArtifactResult {
  const raw = asRecord(rawValue);
  if (!raw) return idleExport;
  return {
    status: statusFromOperation(raw),
    artifactId: asString(raw.artifactId ?? raw.artifact_id ?? raw.id),
    artifactName: asString(raw.artifactName ?? raw.artifact_name ?? raw.name),
    artifactPath: artifactPathFrom(raw),
    files: filesFrom(raw),
    bundle: raw.bundle ?? raw.artifacts,
    raw: rawValue,
  };
}

function buildImportResult(rawValue: unknown): ImportArtifactResult {
  const raw = asRecord(rawValue);
  if (!raw) return idleImport;
  const validationIssues = collectIssues(raw, "import");
  const importedFiles = filesFrom(raw) ?? asArray(raw.importedFiles ?? raw.imported_files).map(String);
  const restoredArtifacts = Object.keys(asRecord(raw.artifacts) ?? {});
  return {
    status: statusFromOperation(raw),
    importedFiles: importedFiles.length > 0 ? importedFiles : undefined,
    restoredArtifacts: restoredArtifacts.length > 0 ? restoredArtifacts : undefined,
    validationIssues,
    raw: rawValue,
  };
}

function buildDiffResult(rawValue: unknown): DiffArtifactResult {
  const raw = asRecord(rawValue);
  if (!raw) return idleDiff;
  const summary = asRecord(raw.summary);
  const issues = collectIssues(raw, "diff");
  return {
    status: statusFromOperation(raw),
    summary: summary ? {
      changed: asNumber(summary.changed),
      added: asNumber(summary.added),
      removed: asNumber(summary.removed),
      unchanged: asNumber(summary.unchanged),
    } : undefined,
    issues,
    comparedArtifacts: asArray(raw.comparedArtifacts ?? raw.compared_artifacts).map(String),
    raw: rawValue,
  };
}

function normalizeLog(value: unknown, index: number): ArtifactOperationLog | null {
  const record = asRecord(value);
  if (!record) return null;
  const operation = String(record.operation ?? "").toLowerCase();
  if (!["export", "import", "diff"].includes(operation)) return null;
  return {
    id: asString(record.id) ?? `artifact-log-${index}`,
    operation: operation as ArtifactOperationKind,
    message: String(record.message ?? "Artifact operation log"),
    status: asStatus(record.status),
    timestamp: asString(record.timestamp),
    evidence: value,
  };
}

function workflowSection(state: unknown): Record<string, unknown> | null {
  const record = asRecord(state);
  if (!record) return null;
  const explicit = asRecord(record.artifactWorkflow ?? record.artifact_workflow);
  if (explicit) return explicit;
  const artifacts = asRecord(record.artifacts);
  return asRecord(artifacts?.artifactWorkflow ?? artifacts?.artifact_workflow);
}

export function buildArtifactWorkflowViewModel(state: unknown): ArtifactWorkflowViewModel {
  const section = workflowSection(state);
  const exportResult = buildExportResult(section?.exportResult ?? section?.export_result ?? section?.export);
  const importResult = buildImportResult(section?.importResult ?? section?.import_result ?? section?.import);
  const diffResult = buildDiffResult(section?.diffResult ?? section?.diff_result ?? section?.diff);
  const issues = [
    ...collectIssues(asRecord(section?.exportResult ?? section?.export), "export"),
    ...importResult.validationIssues,
    ...diffResult.issues,
  ];
  const logs = asArray(section?.logs).map(normalizeLog).filter((log): log is ArtifactOperationLog => log !== null);
  const lastOperation = asString(section?.lastOperation ?? section?.last_operation) as ArtifactOperationKind | undefined;
  const lastStatus = asStatus(section?.lastStatus ?? section?.last_status);

  return {
    exportResult,
    importResult,
    diffResult,
    issues,
    logs,
    summary: {
      lastOperation,
      lastStatus: lastOperation ? lastStatus : undefined,
      issueCount: issues.length,
      logCount: logs.length,
    },
  };
}

export function artifactWorkflowIssuesAsPlatformDiagnostics(vm: ArtifactWorkflowViewModel): PlatformDiagnostic[] {
  return vm.issues
    .filter((issue) => issue.severity !== "info")
    .map((issue) => ({
      code: issue.code ?? `ARTIFACT_${issue.operation.toUpperCase()}`,
      severity: issue.severity === "error" ? "error" : "warning",
      message: issue.message,
      stage: `artifact:${issue.operation}`,
      source: "artifact-workflow",
      phase: "toolchain",
      related_information: [],
      metadata: issue,
    }));
}

export function artifactWorkflowStateForProject(
  projectState: ProjectState | null,
  artifactWorkflow: unknown
): ProjectState | null {
  if (!projectState) return null;
  return { ...projectState, artifactWorkflow };
}
