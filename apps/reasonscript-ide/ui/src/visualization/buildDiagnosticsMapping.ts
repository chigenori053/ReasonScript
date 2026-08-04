/**
 * Maps diagnostics to their pipeline stage.
 * Specification: reasonscript-ide-runtime-visualization/0.1 §12
 */
import type { DiagnosticsMappingViewModel, MappedDiagnostic } from "./viewModels";
import type { PlatformDiagnostic } from "../types";

const PHASE_TO_STAGE: Record<string, string> = {
  parse: "surface_ast",
  semantic: "semantic_ast",
  typecheck: "semantic_ast",
  lowering: "reason_ir",
  ir: "reason_ir",
  execution_plan: "execution_plan",
  runtime: "simulation",
  simulation: "simulation",
  knowledge: "knowledge",
  analyzer: "diagnostics",
  toolchain: "diagnostics",
  lsp: "diagnostics",
};

export function buildDiagnosticsMapping(
  diagnostics: PlatformDiagnostic[]
): DiagnosticsMappingViewModel {
  const byStage: Record<string, MappedDiagnostic[]> = {};

  for (const d of diagnostics) {
    const stage = d.stage ?? PHASE_TO_STAGE[d.phase] ?? "diagnostics";
    const mapped: MappedDiagnostic = {
      pipelineStage: stage,
      code: d.code,
      severity: d.severity,
      message: d.message,
      phase: d.phase,
      span: d.source_range ?? d.span,
    };
    if (!byStage[stage]) byStage[stage] = [];
    byStage[stage].push(mapped);
  }

  return { byStage, totalCount: diagnostics.length };
}
