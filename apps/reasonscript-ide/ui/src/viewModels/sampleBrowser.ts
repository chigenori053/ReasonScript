import type { PlatformDiagnostic } from "../types";

export type SampleBrowserStatus =
  | "idle"
  | "loading"
  | "loaded"
  | "failed"
  | "unavailable";

export type SampleLoadStatus =
  | "idle"
  | "loading"
  | "loaded"
  | "failed"
  | "blocked";

export interface ReasonScriptSample {
  id: string;
  title: string;
  description?: string;
  category?: string;
  source?: string;
  path?: string;
  tags: string[];
  metadata?: unknown;
  raw?: unknown;
}

export interface SampleLoadIssue {
  id: string;
  severity: "error" | "warning" | "info";
  code?: string;
  message: string;
  sampleId?: string;
  evidence?: unknown;
}

export interface SampleOperationLog {
  id: string;
  message: string;
  status?: SampleLoadStatus;
  sampleId?: string;
  timestamp?: string;
  evidence?: unknown;
}

export interface SampleBrowserViewModel {
  status: SampleBrowserStatus;
  samples: ReasonScriptSample[];
  selectedSampleId?: string;
  issues: SampleLoadIssue[];
  logs: SampleOperationLog[];
  summary: {
    sampleCount: number;
    categoryCount: number;
    selectedTitle?: string;
  };
}

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

function statusFrom(value: unknown, samples: ReasonScriptSample[]): SampleBrowserStatus {
  const raw = String(value ?? "").toLowerCase();
  if (["idle", "loading", "loaded", "failed", "unavailable"].includes(raw)) {
    return raw as SampleBrowserStatus;
  }
  return samples.length > 0 ? "loaded" : "unavailable";
}

function sampleCandidates(examplesResult: unknown): unknown[] {
  if (Array.isArray(examplesResult)) return examplesResult;
  const record = asRecord(examplesResult);
  return asArray(record?.examples ?? record?.samples ?? record?.items);
}

function normalizeTags(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String).filter(Boolean).sort();
  const tag = asString(value);
  return tag ? [tag] : [];
}

function normalizeSample(value: unknown, index: number): ReasonScriptSample | null {
  const record = asRecord(value);
  if (!record) return null;
  const id = asString(record.id ?? record.name ?? record.title ?? record.path) ?? `sample-${index}`;
  const title = asString(record.title ?? record.name ?? record.id ?? record.path) ?? id;
  return {
    id,
    title,
    description: asString(record.description),
    category: asString(record.category),
    source: asString(record.source ?? record.code),
    path: asString(record.path),
    tags: normalizeTags(record.tags),
    metadata: record.metadata,
    raw: value,
  };
}

function normalizeIssue(value: unknown, index: number): SampleLoadIssue | null {
  const record = asRecord(value);
  if (!record) return null;
  const rawSeverity = String(record.severity ?? record.level ?? "error").toLowerCase();
  const severity = rawSeverity.includes("warn") ? "warning" : rawSeverity.includes("info") ? "info" : "error";
  return {
    id: asString(record.id) ?? `sample-issue-${index}`,
    severity,
    code: asString(record.code),
    message: String(record.message ?? record.detail ?? "Example loading failed."),
    sampleId: asString(record.sampleId ?? record.sample_id),
    evidence: value,
  };
}

function normalizeLog(value: unknown, index: number): SampleOperationLog | null {
  const record = asRecord(value);
  if (!record) return null;
  const rawStatus = String(record.status ?? "").toLowerCase();
  const status = ["idle", "loading", "loaded", "failed", "blocked"].includes(rawStatus)
    ? rawStatus as SampleLoadStatus
    : undefined;
  return {
    id: asString(record.id) ?? `sample-log-${index}`,
    message: String(record.message ?? "Sample operation log"),
    status,
    sampleId: asString(record.sampleId ?? record.sample_id),
    timestamp: asString(record.timestamp),
    evidence: value,
  };
}

export function buildSampleBrowserViewModel(examplesResult: unknown): SampleBrowserViewModel {
  const record = asRecord(examplesResult);
  const samples = sampleCandidates(examplesResult)
    .map(normalizeSample)
    .filter((sample): sample is ReasonScriptSample => sample !== null);
  const selectedSampleId = asString(record?.selectedSampleId ?? record?.selected_sample_id);
  const selected = samples.find((sample) => sample.id === selectedSampleId);
  const categories = new Set(samples.map((sample) => sample.category).filter(Boolean));
  const issues = asArray(record?.issues ?? record?.errors)
    .map(normalizeIssue)
    .filter((issue): issue is SampleLoadIssue => issue !== null);
  const logs = asArray(record?.logs)
    .map(normalizeLog)
    .filter((log): log is SampleOperationLog => log !== null);

  return {
    status: statusFrom(record?.status, samples),
    samples,
    selectedSampleId,
    issues,
    logs,
    summary: {
      sampleCount: samples.length,
      categoryCount: categories.size,
      selectedTitle: selected?.title,
    },
  };
}

export function sampleBrowserIssuesAsPlatformDiagnostics(vm: SampleBrowserViewModel): PlatformDiagnostic[] {
  return vm.issues
    .filter((issue) => issue.severity !== "info")
    .map((issue) => ({
      code: issue.code ?? "SAMPLE_LOAD_FAILED",
      severity: issue.severity === "error" ? "error" : "warning",
      message: issue.message,
      stage: "sample-browser",
      source: "sample-browser",
      phase: "toolchain",
      related_information: [],
      metadata: issue,
    }));
}
