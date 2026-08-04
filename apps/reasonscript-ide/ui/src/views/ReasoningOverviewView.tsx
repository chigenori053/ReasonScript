import type { CSSProperties, ReactNode } from "react";
import TabPanel from "../components/TabPanel";
import type { ReasoningRuntimeViewModel } from "../types/reasoningOverview";
import JsonArtifactView from "./JsonArtifactView";

interface Props {
  vm: ReasoningRuntimeViewModel;
}

function StatusBadge({ status }: { status: string }) {
  const color = status === "passed" || status === "selected"
    ? "#16a34a"
    : status === "failed" || status === "fatal"
      ? "#dc2626"
      : status === "warning" || status === "partial"
        ? "#d97706"
        : "#64748b";
  return (
    <span style={{ color, fontWeight: 700, textTransform: "uppercase" }}>
      {status || "unknown"}
    </span>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="ide-overview-section">
      <div className="ide-section-title">{title}</div>
      {children}
    </section>
  );
}

function Metric({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="ide-summary-metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function Table({
  columns,
  rows,
  empty,
}: {
  columns: string[];
  rows: ReactNode[][];
  empty: string;
}) {
  if (rows.length === 0) {
    return <div className="ide-muted-note">{empty}</div>;
  }
  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column} style={cellHeaderStyle}>{column}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index}>
              {row.map((cell, cellIndex) => (
                <td key={cellIndex} style={cellStyle}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const cellHeaderStyle: CSSProperties = {
  color: "#94a3b8",
  fontWeight: 600,
  textAlign: "left",
  borderBottom: "1px solid #334155",
  padding: "6px 8px",
};

const cellStyle: CSSProperties = {
  color: "#d1d5db",
  borderBottom: "1px solid #1f2937",
  padding: "6px 8px",
  verticalAlign: "top",
};

function OverviewTab({ vm }: Props) {
  const selectedPath = vm.reasoningPath.paths.find((path) => path.pathId === vm.reasoningPath.selectedPathId);
  return (
    <div className="ide-overview">
      <section className="ide-result-card">
        <div className="ide-section-title">Reasoning Runtime</div>
        <div className="ide-summary-grid">
          <Metric label="Runtime" value={<StatusBadge status={vm.runtimeStatus.status} />} />
          <Metric label="Run" value={vm.runtimeStatus.runId || "unavailable"} />
          <Metric label="Model" value={vm.runtimeStatus.hasReasoningModel ? "available" : "unavailable"} />
          <Metric label="Evaluation" value={vm.runtimeStatus.hasEvaluationReport ? "available" : "unavailable"} />
          <Metric label="Diagnostics" value={`${vm.runtimeStatus.diagnosticCount} total`} />
          <Metric label="Fatal" value={`${vm.runtimeStatus.fatalDiagnosticCount}`} />
        </div>
      </section>

      <Section title="Model Summary">
        {!vm.modelSummary.available ? (
          <div className="ide-muted-note">ReasoningModel unavailable</div>
        ) : (
          <div className="ide-summary-grid">
            <Metric label="Model ID" value={vm.modelSummary.modelId} />
            <Metric label="Selected Path" value={vm.modelSummary.selectedPathId || "unavailable"} />
            <Metric label="Goal" value={vm.modelSummary.evaluationGoal || "unavailable"} />
            <Metric label="Input Units" value={`${vm.modelSummary.inputUnitCount}`} />
            <Metric label="Input Relations" value={`${vm.modelSummary.inputRelationCount}`} />
            <Metric label="Paths" value={`${vm.modelSummary.reasoningPathCount}`} />
            <Metric label="Steps" value={`${vm.modelSummary.reasoningStepCount}`} />
            <Metric label="Knowledge" value={`${vm.modelSummary.knowledgeEmissionCount}`} />
          </div>
        )}
        {vm.modelSummary.requiredChecks.length > 0 && (
          <div className="ide-muted-note">Required checks: {vm.modelSummary.requiredChecks.join(", ")}</div>
        )}
      </Section>

      <Section title="Pipeline Status">
        <div className="ide-summary-grid">
          <Metric label="Status" value={<StatusBadge status={vm.pipelineStatus.status} />} />
          <Metric label="Parser" value={vm.pipelineStatus.parserPassed ? "available" : "unavailable"} />
          <Metric label="Reason IR" value={vm.pipelineStatus.reasonIrAvailable ? "available" : "unavailable"} />
          <Metric label="ExecutionPlan" value={vm.pipelineStatus.executionPlanAvailable ? "available" : "unavailable"} />
          <Metric label="Simulation" value={vm.pipelineStatus.simulationAvailable ? "available" : "unavailable"} />
          <Metric label="Knowledge" value={vm.pipelineStatus.knowledgeAvailable ? "available" : "unavailable"} />
        </div>
      </Section>

      <Section title="Selected Reasoning Path">
        <div className="ide-muted-note">
          Path: {vm.reasoningPath.selectedPathId || "unavailable"} | Signature: {vm.reasoningPath.selectedPathSignature || "unavailable"}
        </div>
        <Table
          columns={["step_id", "step_type", "path"]}
          empty="No reasoning path steps generated."
          rows={(selectedPath?.steps ?? []).map((step) => [
            step.stepId,
            step.stepType,
            `${step.source} --${step.operation}--> ${step.target}`,
          ])}
        />
      </Section>

      <Section title="Evaluation Report">
        {!vm.evaluationReport.available ? (
          <div className="ide-muted-note">EvaluationReport unavailable</div>
        ) : (
          <>
            <div className="ide-summary-grid">
              <Metric label="Status" value={<StatusBadge status={vm.evaluationReport.status} />} />
              <Metric label="Passed" value={vm.evaluationReport.passed ? "true" : "false"} />
              <Metric label="Required" value={vm.evaluationReport.requiredChecksPassed ? "passed" : "failed"} />
              <Metric label="Checks" value={`${vm.evaluationReport.passedChecks}/${vm.evaluationReport.totalChecks}`} />
              <Metric label="Failed" value={`${vm.evaluationReport.failedChecks}`} />
              <Metric label="Warnings" value={`${vm.evaluationReport.warningChecks}`} />
            </div>
            <Table
              columns={["check_type", "required", "status", "message"]}
              empty="No evaluation checks generated."
              rows={vm.evaluationReport.checks.map((check) => [
                check.checkType,
                check.required ? "true" : "false",
                <StatusBadge status={check.status} />,
                check.message,
              ])}
            />
          </>
        )}
      </Section>
    </div>
  );
}

function InputTab({ vm }: Props) {
  return (
    <div className="ide-overview">
      <Section title="Input State">
        <div className="ide-muted-note">
          Input: {vm.inputState.inputId || "unavailable"} | Kind: {vm.inputState.inputKind || "unavailable"}
        </div>
        <Table
          columns={["unit_id", "unit_type", "value"]}
          empty="No input state units were projected."
          rows={vm.inputState.units.map((unit) => [unit.unitId, unit.unitType, JSON.stringify(unit.value)])}
        />
      </Section>
      <Section title="Input Relations">
        <Table
          columns={["relation_id", "relation_type", "source", "target"]}
          empty="No input state relations were projected."
          rows={vm.inputState.relations.map((relation) => [
            relation.relationId,
            relation.relationType,
            relation.source,
            relation.target,
          ])}
        />
      </Section>
    </div>
  );
}

function KnowledgeTab({ vm }: Props) {
  return (
    <div className="ide-overview">
      <Section title="Knowledge Emissions">
        <Table
          columns={["knowledge_id", "source_step_id", "relation", "target", "evidence_path", "path_signature"]}
          empty="No knowledge emissions generated."
          rows={vm.knowledgeEmission.emissions.map((item) => [
            item.knowledgeId,
            item.sourceStepId,
            `${item.source} --${item.relation}--> ${item.target}`,
            item.target,
            item.evidencePath.join(", "),
            item.pathSignature,
          ])}
        />
      </Section>
    </div>
  );
}

function DiagnosticsTab({ vm }: Props) {
  const groups = ["runtime", "reasoning_model", "evaluation_report"] as const;
  return (
    <div className="ide-overview">
      <section className="ide-result-card">
        <div className="ide-section-title">Reasoning Diagnostics</div>
        <div className="ide-summary-grid">
          <Metric label="Total" value={`${vm.diagnostics.total}`} />
          <Metric label="Fatal" value={`${vm.diagnostics.fatal}`} />
          <Metric label="Errors" value={`${vm.diagnostics.error}`} />
          <Metric label="Warnings" value={`${vm.diagnostics.warning}`} />
          <Metric label="Info" value={`${vm.diagnostics.info}`} />
        </div>
      </section>
      {groups.map((source) => (
        <Section key={source} title={source.replace("_", " ")}>
          <Table
            columns={["severity", "code", "location", "message"]}
            empty="No diagnostics."
            rows={vm.diagnostics.items
              .filter((item) => item.source === source)
              .map((item) => [
                <StatusBadge status={item.severity} />,
                item.code,
                item.location ?? "",
                item.message,
              ])}
          />
        </Section>
      ))}
    </div>
  );
}

export default function ReasoningOverviewView({ vm }: Props) {
  return (
    <TabPanel
      defaultTab="overview"
      tabs={[
        { id: "overview", label: "Overview", content: <OverviewTab vm={vm} /> },
        { id: "input", label: "Input State", content: <InputTab vm={vm} /> },
        { id: "knowledge", label: "Knowledge", content: <KnowledgeTab vm={vm} /> },
        { id: "diagnostics", label: "Diagnostics", content: <DiagnosticsTab vm={vm} /> },
        {
          id: "runtime-json",
          label: "Runtime Result JSON",
          content: <JsonArtifactView label="Runtime Result JSON" data={vm.rawArtifacts.runtimeResult} />,
        },
        {
          id: "model-json",
          label: "ReasoningModel JSON",
          content: <JsonArtifactView label="ReasoningModel JSON" data={vm.rawArtifacts.reasoningModel} />,
        },
        {
          id: "report-json",
          label: "EvaluationReport JSON",
          content: <JsonArtifactView label="EvaluationReport JSON" data={vm.rawArtifacts.evaluationReport} />,
        },
        {
          id: "viewmodel-json",
          label: "ViewModel JSON",
          content: <JsonArtifactView label="ViewModel JSON" data={vm} />,
        },
      ]}
    />
  );
}
