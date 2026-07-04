import type { PlatformDiagnostic } from "../types";

export type LogsGroupKey = "backend" | "analyzer" | "runtime" | "ide";

export interface LogsGroup {
  key: LogsGroupKey;
  label: string;
  entries: string[];
}

function diagnosticKey(diagnostic: PlatformDiagnostic): string {
  const metadata = diagnostic.metadata as Record<string, unknown> | undefined;
  const relativePath =
    (typeof metadata?.relativePath === "string" && metadata.relativePath) ||
    (typeof metadata?.relative_path === "string" && metadata.relative_path) ||
    diagnostic.span?.uri ||
    diagnostic.source_range?.uri ||
    "";
  return [diagnostic.code ?? "", diagnostic.source ?? diagnostic.phase ?? "", relativePath, diagnostic.message].join("|");
}

// De-duplicates diagnostics across every migrated + Phase 5 source by
// (code, source/phase, relativePath, message), preserving first-seen order.
export function mergeProblemsSources(sources: PlatformDiagnostic[][]): PlatformDiagnostic[] {
  const seen = new Set<string>();
  const merged: PlatformDiagnostic[] = [];
  for (const list of sources) {
    for (const diagnostic of list) {
      const key = diagnosticKey(diagnostic);
      if (seen.has(key)) continue;
      seen.add(key);
      merged.push(diagnostic);
    }
  }
  return merged;
}

export function buildLogsGroups(input: {
  backend?: string[];
  analyzer?: string[];
  runtime?: string[];
  ide?: string[];
}): LogsGroup[] {
  return [
    { key: "backend", label: "Backend", entries: input.backend ?? [] },
    { key: "analyzer", label: "Analyzer", entries: input.analyzer ?? [] },
    { key: "runtime", label: "Runtime", entries: input.runtime ?? [] },
    { key: "ide", label: "IDE", entries: input.ide ?? [] },
  ];
}
