/**
 * Builds an ExecutionPlanViewModel from the raw execution_plan artifact.
 * Specification: reasonscript-ide-runtime-visualization/0.1 §9
 */
import type { ExecutionPlanViewModel, ExecutionPlanStepViewModel } from "./viewModels";

function inferOperationType(source: string, target: string, transitionId?: string): string {
  if (transitionId?.includes(".return.")) return "function_return";
  if (transitionId?.includes("-result")) return "calculation_result";
  if (source.endsWith("Start")) return "initial_state";
  if (target.includes(".state.result")) return "result_projection";
  return "transition";
}

export function buildExecutionPlanFlow(raw: unknown): ExecutionPlanViewModel {
  if (raw == null) return {
    status: "unavailable",
    steps: [],
    selectedBranches: [],
    alternativePaths: [],
  };

  const ep = raw as Record<string, unknown>;

  if (ep.reachable === false) {
    return {
      status: "failed",
      goalTarget: ep.goal as string | undefined,
      reachable: false,
      steps: [],
      selectedBranches: [],
      alternativePaths: [],
      failureReason: "Goal is unreachable from initial state.",
    };
  }

  const rawSteps = Array.isArray(ep.selected_steps)
    ? (ep.selected_steps as Record<string, unknown>[])
    : [];

  const steps: ExecutionPlanStepViewModel[] = rawSteps.map((s, i) => ({
    index: i + 1,
    stepId: (s.step_id as string) ?? `step-${i + 1}`,
    source: (s.source as string) ?? "",
    target: (s.target as string) ?? "",
    transitionId: s.transition_id as string | undefined,
    operationType: inferOperationType(
      s.source as string ?? "",
      s.target as string ?? "",
      s.transition_id as string | undefined
    ),
    selectedBranch: ep.selected_branch as string | undefined,
    pathSignature: ep.path_signature as string | undefined,
  }));

  const rawAlts = Array.isArray(ep.alternative_paths)
    ? (ep.alternative_paths as Record<string, unknown>[])
    : [];

  const alternativePaths = rawAlts.map((alt) => ({
    stepIds: Array.isArray(alt.step_ids) ? (alt.step_ids as string[]) : [],
    cost: alt.expected_cost as number | undefined,
  }));

  return {
    status: "success",
    goalTarget: ep.goal as string | undefined,
    distance: ep.distance as number | undefined,
    reachable: true,
    pathSignature: ep.path_signature as string | undefined,
    steps,
    selectedBranch: ep.selected_branch as string | undefined,
    selectedBranches: Array.isArray(ep.selected_branches)
      ? (ep.selected_branches as string[])
      : [],
    alternativePaths,
    expectedCost: ep.expected_cost as number | undefined,
  };
}
