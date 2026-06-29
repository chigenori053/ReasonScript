/**
 * View model types for the ReasonScript IDE Runtime Visualization.
 * Specification: reasonscript-ide-runtime-visualization/0.1 §16
 */

// ---------------------------------------------------------------------------
// Pipeline Overview
// ---------------------------------------------------------------------------

export type PipelineStageStatus =
  | "success"
  | "warning"
  | "error"
  | "skipped"
  | "not_available";

export interface PipelineStageViewModel {
  id: string;
  label: string;
  status: PipelineStageStatus;
  summary: string;
  count?: number;
}

export interface PipelineMetrics {
  modelCount: number;
  calculationCount: number;
  functionCount: number;
  runtimeOperationCount: number;
  reasonIrNodeCount: number;
  executionPlanDistance: number | null;
  simulationStepCount: number;
  knowledgeItemCount: number;
  diagnosticCount: number;
}

export interface PipelineOverviewViewModel {
  stages: PipelineStageViewModel[];
  metrics: PipelineMetrics;
}

// ---------------------------------------------------------------------------
// Source Model
// ---------------------------------------------------------------------------

export type ConstructStatus = "preferred" | "compatible" | "reserved";

export interface SourceDeclarationViewModel {
  kind:
    | "function"
    | "calculation"
    | "state"
    | "goal"
    | "constraint"
    | "transition"
    | "struct"
    | "enum"
    | "const"
    | "other";
  name: string;
  signature?: string;
}

export interface SourceModelEntryViewModel {
  construct: string;
  name: string;
  status: ConstructStatus;
  declarations: SourceDeclarationViewModel[];
}

export interface SourceModelViewModel {
  entries: SourceModelEntryViewModel[];
}

// ---------------------------------------------------------------------------
// Execution Plan
// ---------------------------------------------------------------------------

export interface ExecutionPlanStepViewModel {
  index: number;
  stepId: string;
  source: string;
  target: string;
  transitionId?: string;
  operationType: string;
  selectedBranch?: string;
  pathSignature?: string;
  cost?: number;
  confidence?: number;
}

export interface ExecutionPlanViewModel {
  status: "success" | "failed" | "not_available";
  goalTarget?: string;
  distance?: number;
  reachable?: boolean;
  pathSignature?: string;
  steps: ExecutionPlanStepViewModel[];
  selectedBranch?: string;
  selectedBranches: string[];
  alternativePaths: Array<{ stepIds: string[]; cost?: number }>;
  expectedCost?: number;
  failureReason?: string;
}

// ---------------------------------------------------------------------------
// Simulation Trace
// ---------------------------------------------------------------------------

export type SimulationEventType =
  | "start"
  | "transition"
  | "branch_selection"
  | "calculation_result"
  | "function_return"
  | "runtime_input"
  | "runtime_output"
  | "simulation_error"
  | "unknown";

export interface SimulationTraceStepViewModel {
  index: number;
  eventType: SimulationEventType;
  state?: string;
  transition?: string;
  selectedBranch?: string;
  condition?: string;
  conditionValue?: unknown;
  emittedOutput?: string;
  raw: unknown;
}

export interface SimulationTraceViewModel {
  status: "success" | "failed" | "not_available";
  goalReached: boolean;
  finalState?: string;
  stepCount: number;
  selectedBranch?: string;
  pathSignature?: string;
  confidence?: number;
  cost?: number;
  steps: SimulationTraceStepViewModel[];
}

// ---------------------------------------------------------------------------
// Knowledge Evidence
// ---------------------------------------------------------------------------

export interface KnowledgeEvidenceViewModel {
  id: string;
  source: string;
  relation: string;
  target: string;
  confidence?: number;
  evidencePath: string[];
  pathSignature?: string;
  branchId?: string;
  pathLength?: number;
  transitions: string[];
}

export interface KnowledgeViewModel {
  status: "success" | "empty" | "not_available";
  knowledgeCount: number;
  evidenceCount: number;
  items: KnowledgeEvidenceViewModel[];
}

// ---------------------------------------------------------------------------
// Diagnostics Mapping
// ---------------------------------------------------------------------------

export interface MappedDiagnostic {
  pipelineStage: string;
  code?: string;
  severity: string;
  message: string;
  phase: string;
  span?: unknown;
}

export interface DiagnosticsMappingViewModel {
  byStage: Record<string, MappedDiagnostic[]>;
  totalCount: number;
}

// ---------------------------------------------------------------------------
// Runtime Operations
// ---------------------------------------------------------------------------

export interface RuntimeOperationViewModel {
  index: number;
  operation: string;
  sourceConstruct?: string;
  inputState?: string;
  outputState?: string;
  status: "success" | "error" | "not_available";
  emittedEvent?: string;
}
