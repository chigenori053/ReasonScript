import type { ProjectState } from "../types";
import type {
  ReasoningDiagnosticItemViewModel,
  ReasoningRuntimeViewModel,
} from "../types/reasoningOverview";

const SCHEMA = "reasonscript-playground-reasoning-overview/1.0" as const;
const SEVERITY_ORDER: Record<string, number> = { fatal: 0, error: 1, warning: 2, info: 3 };

const unavailable: ReasoningRuntimeViewModel = {
  schemaVersion: SCHEMA,
  sourceRef: { sourceId: "unavailable", sourceKind: "unknown" },
  runtimeStatus: {
    status: "unknown",
    runId: "",
    hasReasoningModel: false,
    hasEvaluationReport: false,
    diagnosticCount: 0,
    fatalDiagnosticCount: 0,
  },
  modelSummary: {
    available: false,
    modelId: "ReasoningModel unavailable",
    modelSchemaVersion: "",
    selectedPathId: "",
    inputUnitCount: 0,
    inputRelationCount: 0,
    reasoningPathCount: 0,
    reasoningStepCount: 0,
    knowledgeEmissionCount: 0,
    evaluationGoal: "",
    requiredChecks: [],
  },
  pipelineStatus: {
    status: "unknown",
    parserPassed: false,
    reasonIrAvailable: false,
    executionPlanAvailable: false,
    simulationAvailable: false,
    knowledgeAvailable: false,
    diagnosticsCount: 0,
  },
  inputState: { inputId: "", inputKind: "", units: [], relations: [] },
  reasoningPath: { selectedPathId: "", selectedPathSignature: "", paths: [] },
  knowledgeEmission: { emissions: [] },
  evaluationReport: {
    available: false,
    reportId: "EvaluationReport unavailable",
    status: "unknown",
    passed: false,
    requiredChecksPassed: false,
    totalChecks: 0,
    passedChecks: 0,
    failedChecks: 0,
    warningChecks: 0,
    fatalDiagnostics: 0,
    checks: [],
  },
  diagnostics: { total: 0, fatal: 0, error: 0, warning: 0, info: 0, items: [] },
  rawArtifacts: {},
};

export function buildReasoningOverviewViewModel(projectState: ProjectState | null): ReasoningRuntimeViewModel {
  const backendVm = asRecord(projectState?.reasoning_overview);
  if (backendVm?.schemaVersion === SCHEMA) {
    const vm = backendVm as unknown as ReasoningRuntimeViewModel;
    return {
      ...vm,
      rawArtifacts: {
        ...(vm.rawArtifacts ?? {}),
        viewModel: vm,
      },
    };
  }

  const runtime = asRecord(projectState?.reasoning_runtime);
  if (!runtime) {
    return {
      ...unavailable,
      rawArtifacts: {
        runtimeResult: projectState?.reasoning_runtime as Record<string, unknown> | undefined,
        reasoningModel: projectState?.reasoning_model as Record<string, unknown> | undefined,
        evaluationReport: projectState?.reasoning_evaluation_report as Record<string, unknown> | undefined,
      },
    };
  }

  const model = asRecord(runtime.reasoning_model) ?? asRecord(projectState?.reasoning_model) ?? {};
  const report = asRecord(runtime.evaluation_report) ?? asRecord(projectState?.reasoning_evaluation_report) ?? {};
  const diagnostics = collectDiagnostics(runtime, model, report);
  const input = asRecord(model.input_state) ?? {};
  const paths = asArray(model.reasoning_paths).filter(isRecord);
  const selectedPathId = text(model.selected_path_id);
  const selectedPath = paths.find((path) => text(path.path_id) === selectedPathId);
  const steps = paths.flatMap((path) => asArray(path.steps).filter(isRecord));
  const target = asRecord(model.evaluation_target) ?? {};
  const pipeline = asRecord(runtime.pipeline_status) ?? {};
  const summary = asRecord(report.summary) ?? {};

  const vm: ReasoningRuntimeViewModel = {
    schemaVersion: SCHEMA,
    sourceRef: {
      sourceId: text(asRecord(runtime.source_ref)?.source_id) || "unavailable",
      sourceKind: text(asRecord(runtime.source_ref)?.source_kind) || "unknown",
      ...(asRecord(runtime.source_ref)?.source_path ? { sourcePath: text(asRecord(runtime.source_ref)?.source_path) } : {}),
    },
    runtimeStatus: {
      status: runtimeStatus(pipeline.status),
      runId: text(runtime.run_id),
      hasReasoningModel: Object.keys(model).length > 0,
      hasEvaluationReport: Object.keys(report).length > 0,
      diagnosticCount: diagnostics.length,
      fatalDiagnosticCount: diagnostics.filter((item) => item.severity === "fatal").length,
    },
    modelSummary: {
      available: Object.keys(model).length > 0,
      modelId: text(model.model_id) || "ReasoningModel unavailable",
      modelSchemaVersion: text(model.schema_version),
      selectedPathId,
      inputUnitCount: asArray(input.units).length,
      inputRelationCount: asArray(input.relations).length,
      reasoningPathCount: paths.length,
      reasoningStepCount: steps.length,
      knowledgeEmissionCount: asArray(model.knowledge_emissions).length,
      evaluationGoal: text(target.goal),
      requiredChecks: asArray(target.required_checks).map(text),
    },
    pipelineStatus: {
      status: runtimeStatus(pipeline.status),
      parserPassed: Boolean(pipeline.parser_passed),
      reasonIrAvailable: Boolean(pipeline.reason_ir_available),
      executionPlanAvailable: Boolean(pipeline.execution_plan_available),
      simulationAvailable: Boolean(pipeline.simulation_available),
      knowledgeAvailable: Boolean(pipeline.knowledge_available),
      diagnosticsCount: numberValue(pipeline.diagnostics_count),
    },
    inputState: {
      inputId: text(input.input_id),
      inputKind: text(input.input_kind),
      units: asArray(input.units).filter(isRecord).map((unit) => ({
        unitId: text(unit.unit_id),
        unitType: text(unit.unit_type),
        value: unit.value,
      })),
      relations: asArray(input.relations).filter(isRecord).map((relation) => ({
        relationId: text(relation.relation_id),
        relationType: text(relation.relation_type),
        source: text(relation.source),
        target: text(relation.target),
      })),
    },
    reasoningPath: {
      selectedPathId,
      selectedPathSignature: text(selectedPath?.path_signature),
      paths: paths.map((path) => ({
        pathId: text(path.path_id),
        pathSignature: text(path.path_signature),
        status: pathStatus(path.status),
        steps: asArray(path.steps).filter(isRecord).map((step) => ({
          stepId: text(step.step_id),
          stepType: text(step.step_type),
          source: text(step.source),
          operation: text(step.operation),
          target: text(step.target),
          evidenceRefs: asArray(step.evidence_refs).map(text),
        })),
      })),
    },
    knowledgeEmission: {
      emissions: asArray(model.knowledge_emissions).filter(isRecord).map((item) => ({
        knowledgeId: text(item.knowledge_id),
        sourceStepId: text(item.source_step_id),
        relation: text(item.relation),
        source: text(item.source),
        target: text(item.target),
        evidencePath: asArray(item.evidence_path).map(text),
        pathSignature: text(item.path_signature),
      })),
    },
    evaluationReport: {
      available: Object.keys(report).length > 0,
      reportId: text(report.report_id) || "EvaluationReport unavailable",
      status: evalStatus(summary.status),
      passed: Boolean(summary.passed),
      requiredChecksPassed: Boolean(summary.required_checks_passed),
      totalChecks: numberValue(summary.total_checks),
      passedChecks: numberValue(summary.passed_checks),
      failedChecks: numberValue(summary.failed_checks),
      warningChecks: numberValue(summary.warning_checks),
      fatalDiagnostics: numberValue(summary.fatal_diagnostics),
      checks: asArray(report.checks).filter(isRecord).map((check) => ({
        checkId: text(check.check_id),
        checkType: text(check.check_type),
        required: Boolean(check.required),
        status: checkStatus(check.status),
        passed: Boolean(check.passed),
        message: text(check.message),
        evidenceRefs: asArray(check.evidence_refs).map(text),
        details: asRecord(check.details) ?? {},
      })),
    },
    diagnostics: diagnosticsSummary(diagnostics),
    rawArtifacts: {
      runtimeResult: runtime,
      reasoningModel: model,
      evaluationReport: report,
    },
  };
  vm.rawArtifacts.viewModel = vm;
  return vm;
}

function collectDiagnostics(runtime: Record<string, unknown>, model: Record<string, unknown>, report: Record<string, unknown>): ReasoningDiagnosticItemViewModel[] {
  const items = [
    ...diagnosticsFrom("runtime", runtime.diagnostics),
    ...diagnosticsFrom("reasoning_model", model.diagnostics),
    ...diagnosticsFrom("evaluation_report", report.diagnostics),
  ];
  return items.sort((a, b) => {
    return (
      SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity]
      || a.source.localeCompare(b.source)
      || a.code.localeCompare(b.code)
      || (a.location ?? "").localeCompare(b.location ?? "")
      || a.message.localeCompare(b.message)
    );
  });
}

function diagnosticsFrom(source: ReasoningDiagnosticItemViewModel["source"], value: unknown): ReasoningDiagnosticItemViewModel[] {
  return asArray(value).filter(isRecord).map((item) => ({
    source,
    code: text(item.code) || "RO-DIAG-UNKNOWN",
    severity: severity(item.severity),
    message: text(item.message),
    ...(item.location ? { location: text(item.location) } : {}),
  }));
}

function diagnosticsSummary(items: ReasoningDiagnosticItemViewModel[]) {
  return {
    total: items.length,
    fatal: items.filter((item) => item.severity === "fatal").length,
    error: items.filter((item) => item.severity === "error").length,
    warning: items.filter((item) => item.severity === "warning").length,
    info: items.filter((item) => item.severity === "info").length,
    items,
  };
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(asRecord(value));
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function text(value: unknown): string {
  return value == null ? "" : String(value);
}

function numberValue(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function runtimeStatus(value: unknown) {
  return value === "passed" || value === "failed" || value === "partial" || value === "fatal" ? value : "unknown";
}

function pathStatus(value: unknown) {
  return value === "selected" || value === "candidate" || value === "rejected" || value === "failed" ? value : "unknown";
}

function evalStatus(value: unknown) {
  return value === "passed" || value === "failed" || value === "warning" || value === "fatal" ? value : "unknown";
}

function checkStatus(value: unknown) {
  return value === "passed" || value === "failed" || value === "warning" || value === "skipped" || value === "fatal" ? value : "unknown";
}

function severity(value: unknown) {
  return value === "fatal" || value === "error" || value === "warning" || value === "info" ? value : "info";
}
