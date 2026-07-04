import type { PlatformDiagnostic, ProjectState } from "../types";

export type AuditStatus =
  | "pass"
  | "warning"
  | "fail"
  | "unavailable";

export type AuditItemStatus =
  | "connected"
  | "missing"
  | "warning"
  | "error"
  | "unknown";

export type AuditIssueSeverity =
  | "error"
  | "warning"
  | "info";

export interface AuditIssue {
  id: string;
  severity: AuditIssueSeverity;
  code?: string;
  message: string;
  category?: string;
  feature?: string;
  expected?: string;
  actual?: string;
  evidence?: unknown;
}

export interface AuditOperationLog {
  id: string;
  message: string;
  status?: AuditStatus;
  timestamp?: string;
  evidence?: unknown;
}

export interface LanguageAuditMatrixRow {
  id: string;
  category: string;
  feature: string;
  expected: string;
  actual?: string;
  status: AuditItemStatus;
  notes?: string;
  evidence?: unknown;
}

export interface LanguageAuditSummary {
  status: AuditStatus;
  connectedCount: number;
  missingCount: number;
  warningCount: number;
  errorCount: number;
  totalCount: number;
  lastRunAt?: string;
}

export interface LanguageAuditExportResult {
  status: AuditStatus;
  exportPath?: string;
  reportId?: string;
  matrixVersion?: string;
  raw?: unknown;
}

export interface LanguageAuditViewModel {
  summary: LanguageAuditSummary;
  matrix: LanguageAuditMatrixRow[];
  issues: AuditIssue[];
  logs: AuditOperationLog[];
  exportResult?: LanguageAuditExportResult;
  raw?: unknown;
}

const unavailableSummary: LanguageAuditSummary = {
  status: "unavailable",
  connectedCount: 0,
  missingCount: 0,
  warningCount: 0,
  errorCount: 0,
  totalCount: 0,
};

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

function statusFromRaw(value: unknown): AuditItemStatus {
  const raw = String(value ?? "").toLowerCase();
  if (raw === "connected" || raw === "pass") return "connected";
  if (raw === "missing") return "missing";
  if (raw === "partial" || raw === "warning" || raw === "warn") return "warning";
  if (raw === "broken" || raw === "error" || raw === "fail" || raw === "failed") return "error";
  return "unknown";
}

function auditStatusFromCounts(missing: number, warnings: number, errors: number, total: number): AuditStatus {
  if (total === 0) return "unavailable";
  if (errors > 0 || missing > 0) return "fail";
  if (warnings > 0) return "warning";
  return "pass";
}

function categoryFor(feature: string, record: Record<string, unknown>): string {
  return asString(record.category) ?? feature.split(".")[0] ?? "language";
}

function notesFor(record: Record<string, unknown>): string | undefined {
  const failed = asArray(record.checks).filter((check) => asRecord(check)?.ok === false);
  if (failed.length === 0) return asString(record.notes);
  return failed
    .map((check) => {
      const item = asRecord(check) ?? {};
      return String(item.detail ?? item.name ?? "failed check");
    })
    .join("; ");
}

function normalizeRow(value: unknown, index: number): LanguageAuditMatrixRow {
  const record = asRecord(value) ?? {};
  const feature = asString(record.feature ?? record.name) ?? `audit-feature-${index}`;
  const status = statusFromRaw(record.status);
  return {
    id: asString(record.id) ?? feature,
    category: categoryFor(feature, record),
    feature,
    expected: asString(record.expected) ?? "compiler/runtime/IDE integration",
    actual: asString(record.actual ?? record.status),
    status,
    notes: notesFor(record),
    evidence: value,
  };
}

function matrixFrom(raw: Record<string, unknown> | null): Record<string, unknown> | null {
  if (!raw) return null;
  return asRecord(raw.matrix) ?? raw;
}

function severityFor(status: AuditItemStatus): AuditIssueSeverity {
  if (status === "error" || status === "missing") return "error";
  if (status === "warning" || status === "unknown") return "warning";
  return "info";
}

function issueFromRow(row: LanguageAuditMatrixRow, index: number): AuditIssue | null {
  if (row.status === "connected") return null;
  return {
    id: `audit-issue-${index}-${row.id}`,
    severity: severityFor(row.status),
    code: `AUDIT_${row.status.toUpperCase()}`,
    message: `${row.feature} audit status is ${row.status}.`,
    category: row.category,
    feature: row.feature,
    expected: row.expected,
    actual: row.actual,
    evidence: row.evidence,
  };
}

function issueFromRecord(value: unknown, index: number, code: string): AuditIssue {
  const record = asRecord(value) ?? {};
  const severity = String(record.severity ?? record.level ?? "").toLowerCase();
  return {
    id: asString(record.id) ?? `${code.toLowerCase()}-${index}`,
    severity: severity.includes("warn") ? "warning" : "error",
    code: asString(record.code ?? record.phase) ?? code,
    message: String(record.message ?? record.detail ?? "Language audit failure"),
    category: asString(record.category),
    feature: asString(record.feature),
    expected: asString(record.expected),
    actual: asString(record.actual),
    evidence: value,
  };
}

function normalizeLog(value: unknown, index: number): AuditOperationLog | null {
  const record = asRecord(value);
  if (!record) return null;
  return {
    id: asString(record.id) ?? `audit-log-${index}`,
    message: String(record.message ?? "Audit operation log"),
    status: auditStatusFromValue(record.status),
    timestamp: asString(record.timestamp),
    evidence: value,
  };
}

function auditStatusFromValue(value: unknown): AuditStatus | undefined {
  const raw = String(value ?? "").toLowerCase();
  if (["pass", "warning", "fail", "unavailable"].includes(raw)) return raw as AuditStatus;
  if (raw === "success" || raw === "connected") return "pass";
  if (raw === "failed" || raw === "error") return "fail";
  return undefined;
}

function exportResultFrom(value: unknown): LanguageAuditExportResult | undefined {
  const record = asRecord(value);
  if (!record) return undefined;
  const files = asRecord(record.files);
  const matrix = matrixFrom(record);
  return {
    status: record.ok === false ? "fail" : "pass",
    exportPath: asString(record.exportPath ?? record.export_path ?? files?.audit ?? files?.matrix),
    reportId: asString(record.reportId ?? record.report_id),
    matrixVersion: asString(record.matrixVersion ?? record.matrix_version ?? matrix?.schema_version),
    raw: value,
  };
}

function languageAuditSection(state: unknown): Record<string, unknown> | null {
  const record = asRecord(state);
  if (!record) return null;
  return asRecord(record.languageAudit ?? record.language_audit);
}

export function buildLanguageAuditViewModel(auditResult: unknown): LanguageAuditViewModel {
  const section = languageAuditSection(auditResult) ?? asRecord(auditResult);
  const rawResult = section?.auditResult ?? section?.audit_result ?? section?.audit ?? section;
  const rawRecord = asRecord(rawResult);
  const matrix = matrixFrom(rawRecord);
  const rows = asArray(matrix?.features ?? matrix?.rows).map(normalizeRow);
  const explicitSummary = asRecord(matrix?.summary);

  const connectedCount = asNumber(explicitSummary?.connected) ?? rows.filter((row) => row.status === "connected").length;
  const missingCount = asNumber(explicitSummary?.missing) ?? rows.filter((row) => row.status === "missing").length;
  const warningCount = asNumber(explicitSummary?.partial) ?? rows.filter((row) => row.status === "warning" || row.status === "unknown").length;
  const errorCount = asNumber(explicitSummary?.broken) ?? rows.filter((row) => row.status === "error").length;
  const totalCount = asNumber(explicitSummary?.total) ?? rows.length;
  const issues = [
    ...rows.map(issueFromRow).filter((issue): issue is AuditIssue => issue !== null),
    ...asArray(rawRecord?.errors).map((error, index) => issueFromRecord(error, index, "AUDIT_FAILED")),
    ...asArray(asRecord(section?.exportResult ?? section?.export_result)?.errors).map((error, index) => issueFromRecord(error, index, "AUDIT_EXPORT_FAILED")),
  ];
  const isStale = Boolean(section?.stale);
  if (isStale) {
    issues.push({
      id: "audit-stale-result",
      severity: "warning",
      code: "AUDIT_STALE",
      message: "Audit result is stale because the source changed after the last audit run.",
    });
  }

  return {
    summary: {
      status: isStale ? "warning" : auditStatusFromCounts(missingCount, warningCount, errorCount, totalCount),
      connectedCount,
      missingCount,
      warningCount: warningCount + (isStale ? 1 : 0),
      errorCount,
      totalCount,
      lastRunAt: asString(section?.lastRunAt ?? section?.last_run_at ?? matrix?.generated_at),
    },
    matrix: rows,
    issues,
    logs: asArray(section?.logs).map(normalizeLog).filter((log): log is AuditOperationLog => log !== null),
    exportResult: exportResultFrom(section?.exportResult ?? section?.export_result),
    raw: rawResult,
  };
}

export function languageAuditIssuesAsPlatformDiagnostics(vm: LanguageAuditViewModel): PlatformDiagnostic[] {
  return vm.issues
    .filter((issue) => issue.severity !== "info")
    .map((issue) => ({
      code: issue.code ?? "LANGUAGE_AUDIT",
      severity: issue.severity === "error" ? "error" : "warning",
      message: issue.message,
      stage: "language-audit",
      source: "language-audit",
      phase: "toolchain",
      related_information: [],
      metadata: issue,
    }));
}

export function languageAuditStateForProject(
  projectState: ProjectState | null,
  languageAudit: unknown
): ProjectState | null {
  if (!projectState) return null;
  return { ...projectState, languageAudit };
}
