export type ReasoningRuntimeStatus = "passed" | "failed" | "partial" | "fatal" | "unknown";
export type ReasoningPathStatus = "selected" | "candidate" | "rejected" | "failed" | "unknown";
export type ReasoningEvaluationStatus = "passed" | "failed" | "warning" | "fatal" | "unknown";
export type ReasoningCheckStatus = "passed" | "failed" | "warning" | "skipped" | "fatal" | "unknown";
export type ReasoningDiagnosticSeverity = "info" | "warning" | "error" | "fatal";
export type ReasoningDiagnosticSource = "runtime" | "reasoning_model" | "evaluation_report" | "unknown";

export interface ReasoningRuntimeResult {
  schema_version?: string;
  run_id?: string;
  source_ref?: Record<string, unknown>;
  pipeline_status?: Record<string, unknown>;
  reasoning_model?: ReasoningModel;
  evaluation_report?: ReasoningEvaluationReport;
  diagnostics?: unknown[];
  [key: string]: unknown;
}

export interface ReasoningModel {
  schema_version?: string;
  model_id?: string;
  source_ref?: Record<string, unknown>;
  input_state?: Record<string, unknown>;
  reasoning_paths?: unknown[];
  selected_path_id?: string;
  knowledge_emissions?: unknown[];
  evaluation_target?: Record<string, unknown>;
  diagnostics?: unknown[];
  [key: string]: unknown;
}

export interface ReasoningEvaluationReport {
  schema_version?: string;
  report_id?: string;
  model_ref?: Record<string, unknown>;
  evaluation_target_ref?: Record<string, unknown>;
  summary?: Record<string, unknown>;
  checks?: unknown[];
  diagnostics?: unknown[];
  [key: string]: unknown;
}

export interface ReasoningSourceRefViewModel {
  sourceId: string;
  sourceKind: string;
  sourcePath?: string;
}

export interface ReasoningRuntimeStatusViewModel {
  status: ReasoningRuntimeStatus;
  runId: string;
  hasReasoningModel: boolean;
  hasEvaluationReport: boolean;
  diagnosticCount: number;
  fatalDiagnosticCount: number;
}

export interface ReasoningModelSummaryViewModel {
  available?: boolean;
  modelId: string;
  modelSchemaVersion: string;
  selectedPathId: string;
  inputUnitCount: number;
  inputRelationCount: number;
  reasoningPathCount: number;
  reasoningStepCount: number;
  knowledgeEmissionCount: number;
  evaluationGoal: string;
  requiredChecks: string[];
}

export interface ReasoningPipelineStatusViewModel {
  status: ReasoningRuntimeStatus;
  parserPassed: boolean;
  reasonIrAvailable: boolean;
  executionPlanAvailable: boolean;
  simulationAvailable: boolean;
  knowledgeAvailable: boolean;
  diagnosticsCount: number;
}

export interface ReasoningInputUnitViewModel {
  unitId: string;
  unitType: string;
  value: unknown;
}

export interface ReasoningInputRelationViewModel {
  relationId: string;
  relationType: string;
  source: string;
  target: string;
}

export interface ReasoningInputStateViewModel {
  inputId: string;
  inputKind: string;
  units: ReasoningInputUnitViewModel[];
  relations: ReasoningInputRelationViewModel[];
}

export interface ReasoningStepViewModel {
  stepId: string;
  stepType: string;
  source: string;
  operation: string;
  target: string;
  evidenceRefs: string[];
}

export interface ReasoningPathItemViewModel {
  pathId: string;
  pathSignature: string;
  status: ReasoningPathStatus;
  steps: ReasoningStepViewModel[];
}

export interface ReasoningPathViewModel {
  selectedPathId: string;
  selectedPathSignature: string;
  paths: ReasoningPathItemViewModel[];
}

export interface ReasoningKnowledgeEmissionItemViewModel {
  knowledgeId: string;
  sourceStepId: string;
  relation: string;
  source: string;
  target: string;
  evidencePath: string[];
  pathSignature: string;
}

export interface ReasoningKnowledgeEmissionViewModel {
  emissions: ReasoningKnowledgeEmissionItemViewModel[];
}

export interface ReasoningEvaluationCheckViewModel {
  checkId: string;
  checkType: string;
  required: boolean;
  status: ReasoningCheckStatus;
  passed: boolean;
  message: string;
  evidenceRefs: string[];
  details: Record<string, unknown>;
}

export interface ReasoningEvaluationReportViewModel {
  available?: boolean;
  reportId: string;
  status: ReasoningEvaluationStatus;
  passed: boolean;
  requiredChecksPassed: boolean;
  totalChecks: number;
  passedChecks: number;
  failedChecks: number;
  warningChecks: number;
  fatalDiagnostics: number;
  checks: ReasoningEvaluationCheckViewModel[];
}

export interface ReasoningDiagnosticItemViewModel {
  source: ReasoningDiagnosticSource;
  code: string;
  severity: ReasoningDiagnosticSeverity;
  message: string;
  location?: string;
}

export interface ReasoningDiagnosticsViewModel {
  total: number;
  fatal: number;
  error: number;
  warning: number;
  info: number;
  items: ReasoningDiagnosticItemViewModel[];
}

export interface ReasoningRawArtifactsViewModel {
  runtimeResult?: ReasoningRuntimeResult | Record<string, unknown>;
  reasoningModel?: ReasoningModel | Record<string, unknown>;
  evaluationReport?: ReasoningEvaluationReport | Record<string, unknown>;
  viewModel?: unknown;
}

export interface ReasoningRuntimeViewModel {
  schemaVersion: "reasonscript-playground-reasoning-overview/1.0";
  sourceRef: ReasoningSourceRefViewModel;
  runtimeStatus: ReasoningRuntimeStatusViewModel;
  modelSummary: ReasoningModelSummaryViewModel;
  pipelineStatus: ReasoningPipelineStatusViewModel;
  inputState: ReasoningInputStateViewModel;
  reasoningPath: ReasoningPathViewModel;
  knowledgeEmission: ReasoningKnowledgeEmissionViewModel;
  evaluationReport: ReasoningEvaluationReportViewModel;
  diagnostics: ReasoningDiagnosticsViewModel;
  rawArtifacts: ReasoningRawArtifactsViewModel;
}
