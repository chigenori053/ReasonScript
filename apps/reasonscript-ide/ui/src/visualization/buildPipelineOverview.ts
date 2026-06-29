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

function stageStatus(
  data: unknown,
  diagnostics: PlatformDiagnostic[],
  phases: string[]
): PipelineStageStatus {
  if (data == null) return "not_available";
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
      label,
      status: "not_available",
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
      label: "Source",
      status: ps.source_files?.length ? "success" : "not_available",
      summary: `${ps.source_files?.length ?? 0} file(s)`,
    },
    {
      id: "surface_ast",
      label: "Surface AST",
      status: stageStatus(ast, diags, ["parse"]),
      summary: ast ? `${countModules(ast)} construct(s)` : "—",
    },
    {
      id: "semantic_ast",
      label: "Semantic AST",
      status: stageStatus(ps.semantic_ast, diags, ["semantic", "typecheck"]),
      summary: ps.semantic_ast ? "parsed" : "—",
    },
    {
      id: "reason_ir",
      label: "Reason IR",
      status: stageStatus(ir, diags, ["lowering", "ir"]),
      summary: ir
        ? `${Array.isArray(ir.transitions) ? (ir.transitions as unknown[]).length : 0} transition(s)`
        : "—",
    },
    {
      id: "execution_plan",
      label: "Execution Plan",
      status: ep == null
        ? "not_available"
        : ep.reachable === false
        ? "error"
        : stageStatus(ep, diags, ["execution_plan"]),
      summary: ep
        ? ep.reachable
          ? `distance ${ep.distance}`
          : "unreachable"
        : "—",
    },
    {
      id: "simulation",
      label: "Simulation",
      status: sim == null
        ? "not_available"
        : sim.success === false
        ? "error"
        : stageStatus(sim, diags, ["simulation", "runtime"]),
      summary: sim
        ? sim.success
          ? `${sim.step_count ?? 0} step(s)`
          : "failed"
        : "—",
    },
    {
      id: "knowledge",
      label: "Knowledge",
      status: stageStatus(knowledge, diags, ["knowledge"]),
      summary: knowledge
        ? `${knowledge.knowledge_count ?? 0} item(s)`
        : "—",
    },
    {
      id: "diagnostics",
      label: "Diagnostics",
      status: diags.length === 0
        ? "success"
        : hasErrors
        ? "error"
        : "warning",
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
