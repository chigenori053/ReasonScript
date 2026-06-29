/**
 * Maps diagnostics to their pipeline stage.
 * Specification: reasonscript-ide-runtime-visualization/0.1 §12
 */
import type { DiagnosticsMappingViewModel, MappedDiagnostic } from "./viewModels";
import type { PlatformDiagnostic } from "../types";

const PHASE_TO_STAGE: Record<string, string> = {
  parse: "Source / Surface AST",
  semantic: "Semantic AST",
  typecheck: "Semantic AST",
  lowering: "Reason IR",
  ir: "Reason IR",
  execution_plan: "Execution Plan",
  runtime: "Simulation",
  simulation: "Simulation",
  knowledge: "Knowledge",
  analyzer: "IDE Layer",
  toolchain: "IDE Layer",
  lsp: "IDE Layer",
};

export function buildDiagnosticsMapping(
  diagnostics: PlatformDiagnostic[]
): DiagnosticsMappingViewModel {
  const byStage: Record<string, MappedDiagnostic[]> = {};

  for (const d of diagnostics) {
    const stage = PHASE_TO_STAGE[d.phase] ?? "Unknown";
    const mapped: MappedDiagnostic = {
      pipelineStage: stage,
      code: d.code,
      severity: d.severity,
      message: d.message,
      phase: d.phase,
      span: d.span,
    };
    if (!byStage[stage]) byStage[stage] = [];
    byStage[stage].push(mapped);
  }

  return { byStage, totalCount: diagnostics.length };
}
