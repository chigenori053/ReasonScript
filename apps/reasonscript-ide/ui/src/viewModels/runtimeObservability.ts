import type { ProjectState } from "../types";

export type RuntimeDataStatus =
  | "available"
  | "empty"
  | "unavailable"
  | "fallback";

export type RuntimeEventKind =
  | "input"
  | "output"
  | "print"
  | "operation"
  | "calculation"
  | "transition"
  | "simulation"
  | "warning"
  | "unknown";

export interface RuntimeOutputEvent {
  id: string;
  kind: RuntimeEventKind;
  message: string;
  value?: unknown;
  sourceState?: string;
  timestamp?: string;
  stepIndex?: number;
  evidence?: unknown;
}

export interface RuntimeInputState {
  id: string;
  name?: string;
  value?: unknown;
  stateType?: string;
  source?: string;
  consumedBy?: string[];
  evidence?: unknown;
}

export interface CalculationTraceItem {
  id: string;
  name?: string;
  expression?: string;
  result?: unknown;
  dependencies?: string[];
  stepIndex?: number;
  evidence?: unknown;
}

export interface RuntimeTraceStep {
  id: string;
  stepIndex: number;
  event: string;
  source?: string;
  target?: string;
  operation?: string;
  branch?: string;
  stateBefore?: unknown;
  stateAfter?: unknown;
  evidence?: unknown;
}

export interface RuntimeObservabilityViewModel {
  runtimeOutput: {
    status: RuntimeDataStatus;
    events: RuntimeOutputEvent[];
  };
  inputState: {
    status: RuntimeDataStatus;
    states: RuntimeInputState[];
  };
  calculation: {
    status: RuntimeDataStatus;
    items: CalculationTraceItem[];
  };
  runtimeTrace: {
    status: RuntimeDataStatus;
    steps: RuntimeTraceStep[];
    source: "runtime_trace" | "simulation_trace" | "none";
  };
  summary: {
    outputEventCount: number;
    inputStateCount: number;
    calculationCount: number;
    runtimeTraceStepCount: number;
  };
}

const unavailable: RuntimeObservabilityViewModel = {
  runtimeOutput: { status: "unavailable", events: [] },
  inputState: { status: "unavailable", states: [] },
  calculation: { status: "unavailable", items: [] },
  runtimeTrace: { status: "unavailable", steps: [], source: "none" },
  summary: {
    outputEventCount: 0,
    inputStateCount: 0,
    calculationCount: 0,
    runtimeTraceStepCount: 0,
  },
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

function asString(value: unknown): string | undefined {
  return typeof value === "string" ? value : undefined;
}

function asNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function sectionFrom(projectState: unknown, viewKey: string, analyzerKey: string): Record<string, unknown> | null {
  const state = asRecord(projectState);
  if (!state) return null;
  const views = asRecord(state.views);
  const artifacts = asRecord(state.artifacts);
  const pipeline = asRecord(state.pipeline);
  const analyzer = asRecord(state.analyzer ?? state.analysis);
  const analyzerArtifact = asRecord(artifacts?.["analyzer.json"] ?? artifacts?.analyzer);
  return asRecord(views?.[viewKey])
    ?? asRecord(analyzer?.[analyzerKey])
    ?? asRecord(analyzerArtifact?.[analyzerKey])
    ?? asRecord(analyzerArtifact?.[viewKey])
    ?? asRecord(pipeline?.[viewKey])
    ?? null;
}

function statusFor(items: unknown[], present: boolean): RuntimeDataStatus {
  if (!present) return "unavailable";
  return items.length > 0 ? "available" : "empty";
}

function eventKind(value: unknown): RuntimeEventKind {
  const raw = String(value ?? "").toLowerCase();
  if (raw.includes("input")) return "input";
  if (raw.includes("print")) return "print";
  if (raw.includes("output")) return "output";
  if (raw.includes("operation")) return "operation";
  if (raw.includes("calculation")) return "calculation";
  if (raw.includes("transition")) return "transition";
  if (raw.includes("simulation")) return "simulation";
  if (raw.includes("warning")) return "warning";
  return "unknown";
}

function outputMessage(record: Record<string, unknown>): string {
  const value = record.rendered_value ?? record.message ?? record.value ?? record.argument ?? record.target ?? record.kind ?? record.operation;
  return value == null ? "Runtime output event" : String(value);
}

function normalizeOutputEvent(value: unknown, index: number): RuntimeOutputEvent {
  const record = asRecord(value) ?? {};
  return {
    id: asString(record.output_id ?? record.id) ?? `runtime-output-${index}`,
    kind: eventKind(record.kind ?? record.operation ?? record.event ?? record.event_type),
    message: outputMessage(record),
    value: record.rendered_value ?? record.value ?? record.argument ?? record.target,
    sourceState: asString(record.sourceState ?? record.source_state ?? record.state),
    timestamp: asString(record.timestamp ?? record.generated_at),
    stepIndex: asNumber(record.stepIndex ?? record.step_index ?? record.step),
    evidence: value,
  };
}

function buildRuntimeOutput(projectState: unknown): RuntimeObservabilityViewModel["runtimeOutput"] {
  const section = sectionFrom(projectState, "output", "output");
  const state = asRecord(projectState);
  const explicitEvents = asArray(section?.events ?? state?.output_events);
  if (section || "output_events" in (state ?? {})) {
    const events = explicitEvents.map(normalizeOutputEvent);
    return { status: statusFor(events, true), events };
  }
  const operationsSection = sectionFrom(projectState, "runtime_operations", "runtime_operations");
  const operations = asArray(operationsSection?.operations);
  if (operationsSection) {
    const events = operations.map((operation, index) => normalizeOutputEvent(operation, index));
    return { status: statusFor(events, true), events };
  }
  return unavailable.runtimeOutput;
}

function normalizeInputState(value: unknown, index: number): RuntimeInputState {
  const record = asRecord(value) ?? {};
  return {
    id: asString(record.state_id ?? record.id) ?? `input-state-${index}`,
    name: asString(record.name ?? record.argument),
    value: record.value,
    stateType: asString(record.state_type ?? record.stateType ?? record.type),
    source: asString(record.source ?? record.source_state ?? record.sourceState),
    consumedBy: asArray(record.consumedBy ?? record.consumed_by).map(String),
    evidence: value,
  };
}

function buildInputState(projectState: unknown): RuntimeObservabilityViewModel["inputState"] {
  const section = sectionFrom(projectState, "input_state", "input_states")
    ?? sectionFrom(projectState, "input_states", "input_states");
  const state = asRecord(projectState);
  const rawStates = asArray(section?.input_states ?? section?.states ?? state?.input_state);
  if (!section && !("input_state" in (state ?? {}))) return unavailable.inputState;
  const states = rawStates.map(normalizeInputState);
  return { status: statusFor(states, true), states };
}

function normalizeCalculation(value: unknown, index: number): CalculationTraceItem {
  const record = asRecord(value) ?? {};
  const dependencies = asArray(record.dependencies ?? record.inputs).map(String);
  return {
    id: asString(record.id ?? record.name) ?? `calculation-${index}`,
    name: asString(record.name),
    expression: asString(record.expression),
    result: record.result ?? record.output ?? record.output_state,
    dependencies,
    stepIndex: asNumber(record.stepIndex ?? record.step_index ?? record.step),
    evidence: value,
  };
}

function buildCalculation(projectState: unknown): RuntimeObservabilityViewModel["calculation"] {
  const section = sectionFrom(projectState, "calculation", "calculations")
    ?? sectionFrom(projectState, "calculations", "calculations");
  const state = asRecord(projectState);
  const rawItems = asArray(section?.calculations ?? section?.items ?? state?.calculations);
  if (!section && !("calculations" in (state ?? {}))) return unavailable.calculation;
  const items = rawItems.map(normalizeCalculation);
  return { status: statusFor(items, true), items };
}

function normalizeRuntimeTraceStep(value: unknown, index: number): RuntimeTraceStep {
  const record = asRecord(value) ?? {};
  const transition = asRecord(record.transition);
  return {
    id: asString(record.id ?? record.trace_id) ?? `runtime-trace-${index}`,
    stepIndex: asNumber(record.stepIndex ?? record.step_index ?? record.step) ?? index,
    event: asString(record.event ?? record.kind ?? record.event_type) ?? "unknown",
    source: asString(record.source ?? transition?.source),
    target: asString(record.target ?? transition?.target),
    operation: asString(record.operation ?? record.kind),
    branch: asString(record.branch ?? record.selected_branch),
    stateBefore: record.stateBefore ?? record.state_before,
    stateAfter: record.stateAfter ?? record.state_after ?? record.state,
    evidence: value,
  };
}

function simulationTraceFrom(projectState: unknown): unknown[] {
  const state = asRecord(projectState);
  const simulationView = sectionFrom(projectState, "simulation", "simulation");
  const simulationArtifact = asRecord(asRecord(state?.artifacts)?.["simulation.json"]);
  return asArray(
    simulationView?.trace
      ?? simulationArtifact?.trace
      ?? asRecord(state?.simulation)?.trace
  );
}

function buildRuntimeTrace(projectState: unknown): RuntimeObservabilityViewModel["runtimeTrace"] {
  const section = sectionFrom(projectState, "runtime_trace", "runtime_trace");
  const trace = asArray(section?.trace ?? section?.steps);
  if (section) {
    const steps = trace.map(normalizeRuntimeTraceStep);
    return {
      status: statusFor(steps, true),
      steps,
      source: "runtime_trace",
    };
  }
  const simulationTrace = simulationTraceFrom(projectState);
  if (simulationTrace.length > 0) {
    return {
      status: "fallback",
      steps: simulationTrace.map(normalizeRuntimeTraceStep),
      source: "simulation_trace",
    };
  }
  return unavailable.runtimeTrace;
}

export function buildRuntimeObservabilityViewModel(
  analyzeResult: unknown
): RuntimeObservabilityViewModel {
  try {
    const runtimeOutput = buildRuntimeOutput(analyzeResult);
    const inputState = buildInputState(analyzeResult);
    const calculation = buildCalculation(analyzeResult);
    const runtimeTrace = buildRuntimeTrace(analyzeResult);
    return {
      runtimeOutput,
      inputState,
      calculation,
      runtimeTrace,
      summary: {
        outputEventCount: runtimeOutput.events.length,
        inputStateCount: inputState.states.length,
        calculationCount: calculation.items.length,
        runtimeTraceStepCount: runtimeTrace.steps.length,
      },
    };
  } catch {
    return unavailable;
  }
}

export function runtimeStatusLabel(status: RuntimeDataStatus): string {
  if (status === "available") return "available";
  if (status === "empty") return "empty";
  if (status === "fallback") return "fallback-from-simulation";
  return "unavailable";
}

export type RuntimeObservabilityProjectState = ProjectState & {
  views?: unknown;
  artifacts?: unknown;
  pipeline?: unknown;
};
