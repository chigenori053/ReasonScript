/**
 * Builds a SimulationTraceViewModel from the raw simulation artifact.
 * Specification: reasonscript-ide-runtime-visualization/0.1 §10
 */
import type {
  SimulationTraceViewModel,
  SimulationTraceStepViewModel,
  SimulationEventType,
} from "./viewModels";

function normalizeEventType(raw: Record<string, unknown>): SimulationEventType {
  const event = raw.event as string | undefined;
  const eventType = raw.event_type as string | undefined;

  // Explicit event_type from backend takes precedence
  if (eventType) {
    const normalized = eventType.toLowerCase();
    if (normalized.includes("branch")) return "branch_selection";
    if (normalized.includes("calculation")) return "calculation_result";
    if (normalized.includes("function")) return "function_return";
    if (normalized.includes("runtime_output")) return "runtime_output";
    if (normalized.includes("runtime_input")) return "runtime_input";
  }

  if (event === "start") return "start";
  if (event === "transition") return "transition";
  if (event === "branch_selection") return "branch_selection";
  if (event === "runtime_output") return "runtime_output";
  if (event === "runtime_input") return "runtime_input";
  if (event === "error") return "simulation_error";

  return "unknown";
}

export function buildSimulationTrace(raw: unknown): SimulationTraceViewModel {
  if (raw == null) {
    return {
      status: "unavailable",
      goalReached: false,
      stepCount: 0,
      steps: [],
    };
  }

  const sim = raw as Record<string, unknown>;

  if (sim.success === false) {
    return {
      status: "failed",
      goalReached: false,
      finalState: sim.final_state as string | undefined,
      stepCount: (sim.step_count as number) ?? 0,
      selectedBranch: sim.selected_branch as string | undefined,
      pathSignature: sim.path_signature as string | undefined,
      confidence: sim.confidence as number | undefined,
      cost: sim.cost as number | undefined,
      steps: [],
    };
  }

  const traceItems = Array.isArray(sim.trace)
    ? (sim.trace as Record<string, unknown>[])
    : [];

  const steps: SimulationTraceStepViewModel[] = traceItems.map((item, i) => ({
    index: i,
    eventType: normalizeEventType(item),
    state: item.state as string | undefined,
    transition: item.transition as string | undefined,
    selectedBranch: item.branch as string | undefined,
    condition: item.condition as string | undefined,
    conditionValue: item.value,
    emittedOutput: item.output as string | undefined,
    raw: item,
  }));

  return {
    status: "success",
    goalReached: Boolean(sim.goal_reached),
    finalState: sim.final_state as string | undefined,
    stepCount: (sim.step_count as number) ?? steps.length,
    selectedBranch: sim.selected_branch as string | undefined,
    pathSignature: sim.path_signature as string | undefined,
    confidence: sim.confidence as number | undefined,
    cost: sim.cost as number | undefined,
    steps,
  };
}
