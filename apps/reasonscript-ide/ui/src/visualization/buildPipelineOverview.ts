/**
 * Builds a PipelineOverviewViewModel from raw pipeline artifacts.
 * Specification: reasonscript-ide-runtime-visualization/0.1 §6
 */
import type {
  PipelineOverviewViewModel,
  PipelineStageViewModel,
  PipelineStageStatus,
} from "./viewModels";
import type { PlatformDiagnostic, ProjectState } from "../types";

const STAGE_ARTIFACTS: Record<string, string | null> = {
  source: null,
  surface_ast: "ast.json",
  semantic_ast: "semantic_ast.json",
  reason_ir: "reason_ir.json",
  execution_plan: "execution_plan.json",
  simulation: "simulation.json",
  knowledge: "knowledge.json",
  diagnostics: "diagnostics.json",
};

function diagnosticCount(diagnostics: PlatformDiagnostic[], phases: string[]): number {
  return diagnostics.filter((d) => phases.includes(d.phase)).length;
}

function stageStatus(
  data: unknown,
  diagnostics: PlatformDiagnostic[],
  phases: string[]
): PipelineStageStatus {
  if (data == null) return "unavailable";
  const stageDiags = diagnostics.filter((d) => phases.includes(d.phase));
  if (stageDiags.some((d) => d.severity === "error")) return "error";
  if (stageDiags.some((d) => d.severity === "warning")) return "warning";
  return "success";
}

function countDeclarationKind(
  ast: unknown,
  nodeType: string
): number {
  if (!ast || typeof ast !== "object") return 0;
  const modules = (ast as Record<string, unknown>).modules;
  if (!Array.isArray(modules)) return 0;
  let count = 0;
  for (const mod of modules) {
    const body = (mod as Record<string, unknown>).body;
    if (Array.isArray(body)) {
      count += body.filter(
        (n: unknown) =>
          typeof n === "object" &&
          n !== null &&
          (n as Record<string, unknown>).node_type === nodeType
      ).length;
    }
  }
  return count;
}

function countModules(ast: unknown): number {
  if (!ast || typeof ast !== "object") return 0;
  const modules = (ast as Record<string, unknown>).modules;
  return Array.isArray(modules) ? modules.length : 0;
}

export function buildPipelineOverview(
  ps: ProjectState | null
): PipelineOverviewViewModel {
  if (ps == null) {
    const empty: PipelineStageViewModel[] = [
      "Source", "Surface AST", "Semantic AST", "Reason IR",
      "Execution Plan", "Simulation", "Knowledge", "Diagnostics",
    ].map((label) => ({
      id: label.toLowerCase().replace(/ /g, "_"),
      name: label,
      label,
      status: "unavailable",
      artifact: STAGE_ARTIFACTS[label.toLowerCase().replace(/ /g, "_")] ?? null,
      diagnostic_count: 0,
      summary: "—",
    }));
    return {
      stages: empty,
      metrics: {
        modelCount: 0, calculationCount: 0, functionCount: 0,
        runtimeOperationCount: 0, reasonIrNodeCount: 0,
        executionPlanDistance: null, simulationStepCount: 0,
        knowledgeItemCount: 0, diagnosticCount: 0,
      },
    };
  }

  const diags = ps.diagnostics ?? [];
  const ep = ps.execution_plan as Record<string, unknown> | null;
  const sim = ps.simulation as Record<string, unknown> | null;
  const knowledge = ps.knowledge as Record<string, unknown> | null;
  const ir = ps.reason_ir as Record<string, unknown> | null;
  const ast = ps.surface_ast;

  const hasErrors = diags.some((d) => d.severity === "error");

  const stages: PipelineStageViewModel[] = [
    {
      id: "source",
      name: "Source",
      label: "Source",
      status: ps.source_files?.length ? "success" : "unavailable",
      artifact: null,
      diagnostic_count: 0,
      summary: `${ps.source_files?.length ?? 0} file(s)`,
    },
    {
      id: "surface_ast",
      name: "Surface AST",
      label: "Surface AST",
      status: stageStatus(ast, diags, ["parse"]),
      artifact: "ast.json",
      diagnostic_count: diagnosticCount(diags, ["parse"]),
      summary: ast ? `${countModules(ast)} construct(s)` : "—",
    },
    {
      id: "semantic_ast",
      name: "Semantic AST",
      label: "Semantic AST",
      status: stageStatus(ps.semantic_ast, diags, ["semantic", "typecheck"]),
      artifact: "semantic_ast.json",
      diagnostic_count: diagnosticCount(diags, ["semantic", "typecheck"]),
      summary: ps.semantic_ast ? "parsed" : "—",
    },
    {
      id: "reason_ir",
      name: "Reason IR",
      label: "Reason IR",
      status: stageStatus(ir, diags, ["lowering", "ir"]),
      artifact: "reason_ir.json",
      diagnostic_count: diagnosticCount(diags, ["lowering", "ir"]),
      summary: ir
        ? `${Array.isArray(ir.transitions) ? (ir.transitions as unknown[]).length : 0} transition(s)`
        : "—",
    },
    {
      id: "execution_plan",
      name: "ExecutionPlan",
      label: "Execution Plan",
      status: ep == null
        ? "unavailable"
        : ep.reachable === false
        ? "error"
        : stageStatus(ep, diags, ["execution_plan"]),
      artifact: "execution_plan.json",
      diagnostic_count: diagnosticCount(diags, ["execution_plan"]),
      summary: ep
        ? ep.reachable
          ? `distance ${ep.distance}`
          : "unreachable"
        : "—",
    },
    {
      id: "simulation",
      name: "Simulation",
      label: "Simulation",
      status: sim == null
        ? "unavailable"
        : sim.success === false
        ? "error"
        : stageStatus(sim, diags, ["simulation", "runtime"]),
      artifact: "simulation.json",
      diagnostic_count: diagnosticCount(diags, ["simulation", "runtime"]),
      summary: sim
        ? sim.success
          ? `${sim.step_count ?? 0} step(s)`
          : "failed"
        : "—",
    },
    {
      id: "knowledge",
      name: "Knowledge",
      label: "Knowledge",
      status: stageStatus(knowledge, diags, ["knowledge"]),
      artifact: "knowledge.json",
      diagnostic_count: diagnosticCount(diags, ["knowledge"]),
      summary: knowledge
        ? `${knowledge.knowledge_count ?? 0} item(s)`
        : "—",
    },
    {
      id: "diagnostics",
      name: "Diagnostics",
      label: "Diagnostics",
      status: diags.length === 0
        ? "success"
        : hasErrors
        ? "error"
        : "warning",
      artifact: "diagnostics.json",
      diagnostic_count: diags.length,
      summary: `${diags.length} diagnostic(s)`,
      count: diags.length,
    },
  ];

  // Metrics
  const modelCount = countModules(ast);
  const calculationCount = countDeclarationKind(ast, "CalculationNode");
  const functionCount = countDeclarationKind(ast, "FunctionDeclarationNode");

  const irTransitions = ir && Array.isArray(ir.transitions)
    ? (ir.transitions as unknown[]).length
    : 0;

  const epDistance = ep?.distance != null ? Number(ep.distance) : null;
  const simStepCount = sim?.step_count != null ? Number(sim.step_count) : 0;
  const knowledgeCount = knowledge?.knowledge_count != null
    ? Number(knowledge.knowledge_count)
    : 0;

  // Runtime operations: scan simulation trace for runtime events
  const trace = sim && Array.isArray(sim.trace) ? (sim.trace as Record<string, unknown>[]) : [];
  const runtimeOpCount = trace.filter(
    (s) => s.event === "runtime_output" || s.event === "runtime_input"
  ).length;

  return {
    stages,
    metrics: {
      modelCount,
      calculationCount,
      functionCount,
      runtimeOperationCount: runtimeOpCount,
      reasonIrNodeCount: irTransitions,
      executionPlanDistance: epDistance,
      simulationStepCount: simStepCount,
      knowledgeItemCount: knowledgeCount,
      diagnosticCount: diags.length,
    },
  };
}
