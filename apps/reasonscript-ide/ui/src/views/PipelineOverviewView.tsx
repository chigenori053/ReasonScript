/**
 * Pipeline Overview View — single-glance pipeline status.
 * Specification: reasonscript-ide-runtime-visualization/0.1 §6
 */
import type {
  PipelineOverviewViewModel,
  PipelineStageStatus,
} from "../visualization/viewModels";
import type { ArtifactKind } from "../types";

const STATUS_ICON: Record<PipelineStageStatus, string> = {
  success: "✓",
  warning: "⚠",
  error: "✕",
  skipped: "–",
  unavailable: "·",
};

const STATUS_COLOR: Record<PipelineStageStatus, string> = {
  success: "#34d399",
  warning: "#fbbf24",
  error: "#f87171",
  skipped: "#6b7280",
  unavailable: "#374151",
};

const STAGE_TO_ARTIFACT_KIND: Record<string, ArtifactKind | null> = {
  source: "source",
  surface_ast: "surface_ast",
  semantic_ast: "semantic_ast",
  reason_ir: "reason_ir",
  execution_plan: "execution_plan",
  simulation: null,
  knowledge: null,
  diagnostics: "diagnostic",
};

interface Props {
  vm: PipelineOverviewViewModel;
  onNavigate?: (kind: ArtifactKind | null, stageId: string) => void;
}

export default function PipelineOverviewView({ vm, onNavigate }: Props) {
  const { stages, metrics } = vm;

  return (
    <div style={{ overflow: "auto", height: "100%", fontFamily: "monospace" }}>
      {/* Stage list */}
      <div style={{ padding: "12px 0 4px" }}>
        {stages.map((stage) => {
          const color = STATUS_COLOR[stage.status];
          const icon = STATUS_ICON[stage.status];
          const clickable = !!onNavigate;
          return (
            <div
              key={stage.id}
              onClick={clickable ? () => onNavigate?.(STAGE_TO_ARTIFACT_KIND[stage.id] ?? null, stage.id) : undefined}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                padding: "6px 16px",
                cursor: clickable ? "pointer" : "default",
                fontSize: 13,
              }}
            >
              <span style={{ color, minWidth: 14, fontWeight: 700 }}>{icon}</span>
              <span style={{ color: "#d1d5db", minWidth: 130 }}>{stage.label}</span>
              <span style={{ color: color, fontSize: 11, minWidth: 70 }}>
                {stage.status}
              </span>
              <span style={{ color: "#6b7280", fontSize: 11 }}>{stage.summary}</span>
            </div>
          );
        })}
      </div>

      {/* Divider */}
      <div style={{ borderTop: "1px solid #1f2937", margin: "8px 16px" }} />

      {/* Metrics */}
      <div style={{ padding: "4px 16px 16px" }}>
        <div style={{ color: "#6b7280", fontSize: 11, marginBottom: 8, textTransform: "uppercase", letterSpacing: 1 }}>
          Metrics
        </div>
        <MetricGrid metrics={metrics} />
      </div>
    </div>
  );
}

function MetricGrid({ metrics }: { metrics: PipelineOverviewViewModel["metrics"] }) {
  const rows: [string, string][] = [
    ["Model / Module", String(metrics.modelCount)],
    ["Calculations", String(metrics.calculationCount)],
    ["Functions", String(metrics.functionCount)],
    ["Runtime Ops", String(metrics.runtimeOperationCount)],
    ["IR Transitions", String(metrics.reasonIrNodeCount)],
    ["Plan Distance", metrics.executionPlanDistance != null ? String(metrics.executionPlanDistance) : "—"],
    ["Sim Steps", String(metrics.simulationStepCount)],
    ["Knowledge Items", String(metrics.knowledgeItemCount)],
    ["Diagnostics", String(metrics.diagnosticCount)],
  ];

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "4px 0" }}>
      {rows.map(([label, value]) => (
        <div key={label} style={{ display: "contents" }}>
          <span style={{ color: "#6b7280", fontSize: 12, padding: "1px 0" }}>{label}</span>
          <span style={{ color: "#e5e7eb", fontSize: 12, padding: "1px 0" }}>{value}</span>
        </div>
      ))}
    </div>
  );
}
