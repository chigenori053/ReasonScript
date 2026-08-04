import type { PlatformDiagnostic, ProjectState, SourceSpan } from "../types";

export type AnalysisStatus =
  | "pass"
  | "warning"
  | "fail"
  | "unavailable";

export type AnalysisSeverity =
  | "error"
  | "warning"
  | "info";

export interface AnalysisDiagnostic {
  id: string;
  feature: string;
  severity: AnalysisSeverity;
  code?: string;
  message: string;
  stage?: string;
  relativePath?: string;
  sourceRange?: {
    startLine?: number;
    startColumn?: number;
    endLine?: number;
    endColumn?: number;
  };
  evidence?: unknown;
}

export interface AnalysisMetric {
  name: string;
  status: AnalysisStatus;
  value?: number | string | boolean;
  unit?: string;
  summary?: string;
  evidence?: unknown;
}

export interface DiagnosticsAnalysisViewModel {
  strict: {
    status: AnalysisStatus;
    diagnostics: AnalysisDiagnostic[];
  };
  cycle: {
    status: AnalysisStatus;
    diagnostics: AnalysisDiagnostic[];
    cycleCount?: number;
  };
  exhaustiveness: {
    status: AnalysisStatus;
    diagnostics: AnalysisDiagnostic[];
  };
  typeCoverage: {
    status: AnalysisStatus;
    coveragePercent?: number;
    diagnostics: AnalysisDiagnostic[];
  };
  ownership: {
    status: AnalysisStatus;
    diagnostics: AnalysisDiagnostic[];
    producerCount?: number;
    consumerCount?: number;
  };
  determinism: {
    status: AnalysisStatus;
    deterministic?: boolean;
    diagnostics: AnalysisDiagnostic[];
  };
  complexity: {
    status: AnalysisStatus;
    metrics: AnalysisMetric[];
    diagnostics: AnalysisDiagnostic[];
  };
  allDiagnostics: AnalysisDiagnostic[];
}

const unavailable: DiagnosticsAnalysisViewModel = {
  strict: { status: "unavailable", diagnostics: [] },
  cycle: { status: "unavailable", diagnostics: [] },
  exhaustiveness: { status: "unavailable", diagnostics: [] },
  typeCoverage: { status: "unavailable", diagnostics: [] },
  ownership: { status: "unavailable", diagnostics: [] },
  determinism: { status: "unavailable", diagnostics: [] },
  complexity: { status: "unavailable", metrics: [], diagnostics: [] },
  allDiagnostics: [],
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

function asNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function asString(value: unknown): string | undefined {
  return typeof value === "string" ? value : undefined;
}

function normalizeSeverity(value: unknown): AnalysisSeverity {
  const raw = String(value ?? "").toLowerCase();
  if (raw === "error" || raw === "fail" || raw === "fatal") return "error";
  if (raw === "warning" || raw === "warn") return "warning";
  return "info";
}

function statusFromDiagnostics(diagnostics: AnalysisDiagnostic[], passWhenEmpty = true): AnalysisStatus {
  if (diagnostics.some((diagnostic) => diagnostic.severity === "error")) return "fail";
  if (diagnostics.some((diagnostic) => diagnostic.severity === "warning")) return "warning";
  return passWhenEmpty ? "pass" : "unavailable";
}

function sourceRangeFrom(value: unknown): AnalysisDiagnostic["sourceRange"] | undefined {
  const range = asRecord(value);
  if (!range) return undefined;
  return {
    startLine: asNumber(range.startLine ?? range.start_line),
    startColumn: asNumber(range.startColumn ?? range.start_column),
    endLine: asNumber(range.endLine ?? range.end_line),
    endColumn: asNumber(range.endColumn ?? range.end_column),
  };
}

function normalizeDiagnostic(
  value: unknown,
  feature: string,
  index: number,
  defaults: Partial<AnalysisDiagnostic> = {}
): AnalysisDiagnostic {
  const record = asRecord(value) ?? {};
  const message =
    asString(record.message) ??
    asString(record.summary) ??
    asString(record.reason) ??
    `${feature} diagnostic`;
  return {
    id: `${feature.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-${index}`,
    feature,
    severity: normalizeSeverity(record.severity ?? defaults.severity),
    code: asString(record.code ?? defaults.code),
    message,
    stage: asString(record.stage ?? defaults.stage) ?? feature.toLowerCase().replace(/ /g, "_"),
    relativePath: asString(record.relativePath ?? record.relative_path ?? defaults.relativePath),
    sourceRange: sourceRangeFrom(record.sourceRange ?? record.source_range ?? record.span),
    evidence: record.evidence ?? value,
  };
}

function normalizeDiagnostics(
  values: unknown,
  feature: string,
  defaults: Partial<AnalysisDiagnostic> = {}
): AnalysisDiagnostic[] {
  return asArray(values).map((value, index) => normalizeDiagnostic(value, feature, index, defaults));
}

function firstRecord(...values: unknown[]): Record<string, unknown> | null {
  for (const value of values) {
    const record = asRecord(value);
    if (record) return record;
  }
  return null;
}

function sectionFrom(projectState: unknown, viewKey: string, analyzerKey: string): Record<string, unknown> | null {
  const state = asRecord(projectState);
  if (!state) return null;
  const views = asRecord(state.views);
  const analyzer = asRecord(state.analyzer ?? state.analysis);
  const artifacts = asRecord(state.artifacts);
  const analyzerArtifact = asRecord(artifacts?.["analyzer.json"] ?? artifacts?.analyzer);
  return firstRecord(
    views?.[viewKey],
    analyzer?.[analyzerKey],
    analyzerArtifact?.[analyzerKey],
    analyzerArtifact?.[viewKey]
  );
}

function diagnosticsFromExisting(projectState: unknown): AnalysisDiagnostic[] {
  const state = asRecord(projectState);
  const existing = asArray(state?.diagnostics);
  return existing.map((diagnostic, index) => normalizeDiagnostic(
    diagnostic,
    "Compiler diagnostics",
    index,
    { stage: "diagnostics" }
  ));
}

function buildStrict(projectState: unknown): DiagnosticsAnalysisViewModel["strict"] {
  const section = sectionFrom(projectState, "strict_diagnostics", "strict_diagnostics");
  if (!section) return unavailable.strict;
  const diagnostics = normalizeDiagnostics(section.diagnostics, "Strict diagnostics", {
    severity: "warning",
    stage: "strict",
  });
  return { status: statusFromDiagnostics(diagnostics), diagnostics };
}

function buildCycle(projectState: unknown): DiagnosticsAnalysisViewModel["cycle"] {
  const section = sectionFrom(projectState, "cycle", "cycle_validation");
  if (!section) return unavailable.cycle;
  const cycleNodes = asArray(section.cycle_nodes ?? section.nodes);
  const errors = normalizeDiagnostics(section.errors ?? section.diagnostics, "Cycle diagnostics", {
    severity: "error",
    code: "CAL-030",
    stage: "cycle",
  });
  const hasCycle = Boolean(section.has_cycle) || errors.length > 0 || cycleNodes.length > 0;
  const diagnostics = errors.length > 0
    ? errors
    : hasCycle
      ? [normalizeDiagnostic({
          code: "CAL-030",
          message: "Dependency Cycle Detected",
          nodes: cycleNodes,
          severity: "error",
        }, "Cycle diagnostics", 0, { stage: "cycle" })]
      : [];
  return {
    status: hasCycle ? "fail" : "pass",
    diagnostics,
    cycleCount: cycleNodes.length,
  };
}

function buildExhaustiveness(projectState: unknown): DiagnosticsAnalysisViewModel["exhaustiveness"] {
  const section = sectionFrom(projectState, "exhaustiveness", "exhaustiveness");
  if (!section) return unavailable.exhaustiveness;
  const missing = asArray(section.missing ?? section.missing_cases);
  const diagnostics = normalizeDiagnostics(section.diagnostics, "Exhaustiveness", {
    severity: "warning",
    stage: "exhaustiveness",
  });
  if (diagnostics.length === 0 && missing.length > 0) {
    diagnostics.push(normalizeDiagnostic({
      code: "EXH-001",
      message: `Non-exhaustive analysis: ${missing.length} missing case(s)`,
      missing,
      severity: "warning",
    }, "Exhaustiveness", 0, { stage: "exhaustiveness" }));
  }
  const exhaustive = Boolean(section.is_exhaustive ?? section.exhaustive);
  return {
    status: diagnostics.length > 0 ? "warning" : exhaustive ? "pass" : "pass",
    diagnostics,
  };
}

function buildTypeCoverage(projectState: unknown): DiagnosticsAnalysisViewModel["typeCoverage"] {
  const section = sectionFrom(projectState, "type_coverage", "type_coverage");
  if (!section) return unavailable.typeCoverage;
  const coveragePercent = asNumber(section.coveragePercent ?? section.coverage_pct ?? section.coverage);
  const unknownTypes = asArray(section.unknown ?? section.missing_annotations ?? section.missing);
  const diagnostics = normalizeDiagnostics(section.diagnostics, "Type coverage", {
    severity: "warning",
    stage: "type_coverage",
  });
  if (diagnostics.length === 0 && unknownTypes.length > 0) {
    diagnostics.push(normalizeDiagnostic({
      code: "TYPE-001",
      message: `${unknownTypes.length} unknown or missing type annotation(s)`,
      unknown: unknownTypes,
      severity: "warning",
    }, "Type coverage", 0, { stage: "type_coverage" }));
  }
  return {
    status: diagnostics.length > 0 ? "warning" : "pass",
    coveragePercent,
    diagnostics,
  };
}

function buildOwnership(projectState: unknown): DiagnosticsAnalysisViewModel["ownership"] {
  const section = sectionFrom(projectState, "ownership", "ownership");
  if (!section) return unavailable.ownership;
  const entries = asArray(section.entries);
  const conflicts = asArray(section.conflicts ?? section.orphans ?? section.ambiguous);
  const producerCount = entries.filter((entry) => Boolean(asRecord(entry)?.producer)).length;
  const consumerCount = entries.filter((entry) => Boolean(asRecord(entry)?.consumer)).length;
  const diagnostics = normalizeDiagnostics(section.diagnostics ?? conflicts, "Ownership analysis", {
    severity: "warning",
    stage: "ownership",
  });
  return {
    status: diagnostics.length > 0 ? statusFromDiagnostics(diagnostics) : "pass",
    diagnostics,
    producerCount,
    consumerCount,
  };
}

function buildDeterminism(projectState: unknown): DiagnosticsAnalysisViewModel["determinism"] {
  const section = sectionFrom(projectState, "determinism", "determinism");
  if (!section) return unavailable.determinism;
  const nonDeterministicSources = asArray(section.non_deterministic_sources ?? section.nonDeterministicSources);
  const deterministic = Boolean(section.overall_deterministic ?? section.deterministic);
  const diagnostics = normalizeDiagnostics(section.diagnostics, "Determinism", {
    severity: "warning",
    stage: "determinism",
  });
  if (diagnostics.length === 0 && nonDeterministicSources.length > 0) {
    diagnostics.push(...nonDeterministicSources.map((source, index) => normalizeDiagnostic({
      code: "DET-001",
      message: asString(asRecord(source)?.reason) ?? "Non-deterministic source detected",
      severity: "warning",
      evidence: source,
    }, "Determinism", index, { stage: "determinism" })));
  }
  return {
    status: diagnostics.length > 0 ? "warning" : deterministic ? "pass" : "warning",
    deterministic,
    diagnostics,
  };
}

function complexityLevel(section: Record<string, unknown>, metrics: AnalysisMetric[]): AnalysisStatus {
  const explicit = String(section.status ?? section.level ?? "").toLowerCase();
  if (explicit === "high" || explicit === "fail") return "fail";
  if (explicit === "medium" || explicit === "warning") return "warning";
  if (explicit === "low" || explicit === "pass") return "pass";

  const numericValues = metrics
    .map((metric) => (typeof metric.value === "number" ? metric.value : undefined))
    .filter((value): value is number => value != null);
  if (numericValues.some((value) => value > 100)) return "warning";
  return metrics.length > 0 ? "pass" : "unavailable";
}

function buildComplexity(projectState: unknown): DiagnosticsAnalysisViewModel["complexity"] {
  const section = sectionFrom(projectState, "complexity", "complexity");
  if (!section) return unavailable.complexity;
  const metrics: AnalysisMetric[] = Object.entries(section)
    .filter(([name, value]) => typeof value === "number" || typeof value === "string" || typeof value === "boolean")
    .map(([name, value]) => ({
      name,
      status: "pass",
      value: value as number | string | boolean,
      evidence: { [name]: value },
    }));
  const diagnostics = normalizeDiagnostics(section.diagnostics ?? section.thresholds_exceeded, "Complexity", {
    severity: "warning",
    stage: "complexity",
  });
  const status = diagnostics.length > 0 ? statusFromDiagnostics(diagnostics) : complexityLevel(section, metrics);
  return { status, metrics, diagnostics };
}

export function buildDiagnosticsAnalysisViewModel(
  analyzeResult: unknown
): DiagnosticsAnalysisViewModel {
  try {
    const strict = buildStrict(analyzeResult);
    const cycle = buildCycle(analyzeResult);
    const exhaustiveness = buildExhaustiveness(analyzeResult);
    const typeCoverage = buildTypeCoverage(analyzeResult);
    const ownership = buildOwnership(analyzeResult);
    const determinism = buildDeterminism(analyzeResult);
    const complexity = buildComplexity(analyzeResult);
    const allDiagnostics = [
      ...diagnosticsFromExisting(analyzeResult),
      ...strict.diagnostics,
      ...cycle.diagnostics,
      ...exhaustiveness.diagnostics,
      ...typeCoverage.diagnostics,
      ...ownership.diagnostics,
      ...determinism.diagnostics,
      ...complexity.diagnostics,
    ];
    return {
      strict,
      cycle,
      exhaustiveness,
      typeCoverage,
      ownership,
      determinism,
      complexity,
      allDiagnostics,
    };
  } catch {
    return unavailable;
  }
}

function spanFromAnalysis(diagnostic: AnalysisDiagnostic): SourceSpan | undefined {
  const range = diagnostic.sourceRange;
  if (!range) return undefined;
  return {
    uri: diagnostic.relativePath ?? "",
    start_line: range.startLine ?? 0,
    start_column: range.startColumn ?? 0,
    end_line: range.endLine ?? range.startLine ?? 0,
    end_column: range.endColumn ?? range.startColumn ?? 0,
  };
}

export function analysisDiagnosticToPlatformDiagnostic(
  diagnostic: AnalysisDiagnostic
): PlatformDiagnostic {
  const severity = diagnostic.severity === "warning" ? "warning" : diagnostic.severity === "error" ? "error" : "info";
  return {
    code: diagnostic.code,
    severity,
    message: diagnostic.message,
    stage: diagnostic.stage,
    span: spanFromAnalysis(diagnostic),
    phase: "analyzer",
    related_information: [],
    metadata: {
      analysis_feature: diagnostic.feature,
      relative_path: diagnostic.relativePath,
      evidence: diagnostic.evidence,
    },
  };
}

export function migratedAnalysisDiagnosticsAsPlatformDiagnostics(
  vm: DiagnosticsAnalysisViewModel
): PlatformDiagnostic[] {
  return vm.allDiagnostics.map(analysisDiagnosticToPlatformDiagnostic);
}

export function analysisStatusLabel(status: AnalysisStatus): string {
  if (status === "pass") return "pass";
  if (status === "warning") return "warning";
  if (status === "fail") return "fail";
  return "unavailable";
}

export function typeCoverageLabel(vm: DiagnosticsAnalysisViewModel): string {
  return vm.typeCoverage.coveragePercent == null
    ? "unavailable"
    : `${vm.typeCoverage.coveragePercent}%`;
}

export function complexitySummaryLabel(vm: DiagnosticsAnalysisViewModel): string {
  if (vm.complexity.status === "unavailable") return "unavailable";
  if (vm.complexity.status === "fail") return "high";
  if (vm.complexity.status === "warning") return "medium";
  return "low";
}

export type DiagnosticsAnalysisProjectState = ProjectState & {
  views?: unknown;
  artifacts?: unknown;
  pipeline?: unknown;
};
