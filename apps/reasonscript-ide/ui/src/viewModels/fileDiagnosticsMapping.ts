import type { PlatformDiagnostic } from "../types";

export type IdeDiagnosticSeverity = "error" | "warning" | "info";

export interface IdeSourceRange {
  startLine?: number;
  startColumn?: number;
  endLine?: number;
  endColumn?: number;
}

export type IdeDiagnosticSource =
  | "compiler"
  | "semantic"
  | "runtime"
  | "artifact"
  | "audit"
  | "workspace"
  | "sample"
  | "unknown";

export interface IdeDiagnostic {
  id: string;
  severity: IdeDiagnosticSeverity;
  code?: string;
  message: string;
  source: IdeDiagnosticSource;
  relativePath?: string;
  sourceRange?: IdeSourceRange;
  stage?: string;
  evidence?: unknown;
}

export const UNKNOWN_PATH_GROUP = "__unknown__";

export type DiagnosticScope = "current" | "workspace" | "all";

export interface FileDiagnosticsGroup {
  relativePath: string;
  diagnostics: IdeDiagnostic[];
  errorCount: number;
  warningCount: number;
}

export interface FileDiagnosticsMapping {
  groups: FileDiagnosticsGroup[];
  byPath: Record<string, FileDiagnosticsGroup>;
  activeRelativePath?: string;
}

function normalizeSeverity(severity: PlatformDiagnostic["severity"]): IdeDiagnosticSeverity {
  if (severity === "error") return "error";
  if (severity === "warning") return "warning";
  return "info";
}

function normalizeSource(diagnostic: PlatformDiagnostic): IdeDiagnosticSource {
  const raw = diagnostic.source ?? diagnostic.phase;
  switch (raw) {
    case "workspace":
      return "workspace";
    case "runtime":
    case "simulation":
      return "runtime";
    case "analyzer":
      return "artifact";
    case "semantic":
    case "typecheck":
      return "semantic";
    case "parse":
    case "lowering":
    case "ir":
      return "compiler";
    default:
      return "unknown";
  }
}

function relativePathFromDiagnostic(diagnostic: PlatformDiagnostic): string | undefined {
  const metadata = diagnostic.metadata as Record<string, unknown> | undefined;
  const fromMetadata =
    typeof metadata?.relativePath === "string"
      ? metadata.relativePath
      : typeof metadata?.relative_path === "string"
        ? (metadata.relative_path as string)
        : undefined;
  const fromSpan = diagnostic.span?.uri || diagnostic.source_range?.uri;
  return fromMetadata ?? (fromSpan || undefined);
}

function sourceRangeFromDiagnostic(diagnostic: PlatformDiagnostic): IdeSourceRange | undefined {
  const span = diagnostic.span ?? diagnostic.source_range ?? undefined;
  if (!span) return undefined;
  return {
    startLine: span.start_line,
    startColumn: span.start_column,
    endLine: span.end_line,
    endColumn: span.end_column,
  };
}

export function toIdeDiagnostic(diagnostic: PlatformDiagnostic, index: number): IdeDiagnostic {
  return {
    id: `${diagnostic.code ?? diagnostic.stage ?? "diagnostic"}-${index}`,
    severity: normalizeSeverity(diagnostic.severity),
    code: diagnostic.code,
    message: diagnostic.message,
    source: normalizeSource(diagnostic),
    relativePath: relativePathFromDiagnostic(diagnostic),
    sourceRange: sourceRangeFromDiagnostic(diagnostic),
    stage: diagnostic.stage,
    evidence: diagnostic.metadata,
  };
}

export function buildFileDiagnosticsMapping(
  diagnostics: PlatformDiagnostic[],
  activeRelativePath?: string | null
): FileDiagnosticsMapping {
  const byPath: Record<string, FileDiagnosticsGroup> = {};

  diagnostics.forEach((diagnostic, index) => {
    const ideDiagnostic = toIdeDiagnostic(diagnostic, index);
    const key = ideDiagnostic.relativePath ?? UNKNOWN_PATH_GROUP;
    if (!byPath[key]) {
      byPath[key] = { relativePath: key, diagnostics: [], errorCount: 0, warningCount: 0 };
    }
    byPath[key].diagnostics.push(ideDiagnostic);
    if (ideDiagnostic.severity === "error") byPath[key].errorCount += 1;
    if (ideDiagnostic.severity === "warning") byPath[key].warningCount += 1;
  });

  return {
    groups: Object.values(byPath),
    byPath,
    activeRelativePath: activeRelativePath ?? undefined,
  };
}

export function filterByScope(
  mapping: FileDiagnosticsMapping,
  scope: DiagnosticScope
): IdeDiagnostic[] {
  const all = mapping.groups.flatMap((group) => group.diagnostics);
  if (scope === "all") return all;
  if (scope === "current") {
    if (!mapping.activeRelativePath) return [];
    return mapping.byPath[mapping.activeRelativePath]?.diagnostics ?? [];
  }
  // "workspace": every diagnostic attributable to a known file, excluding the unknown bucket
  return mapping.groups
    .filter((group) => group.relativePath !== UNKNOWN_PATH_GROUP)
    .flatMap((group) => group.diagnostics);
}

export function severityBadgeForPath(
  mapping: FileDiagnosticsMapping,
  relativePath: string
): IdeDiagnosticSeverity | null {
  const group = mapping.byPath[relativePath];
  if (!group) return null;
  if (group.errorCount > 0) return "error";
  if (group.warningCount > 0) return "warning";
  return group.diagnostics.length > 0 ? "info" : null;
}
