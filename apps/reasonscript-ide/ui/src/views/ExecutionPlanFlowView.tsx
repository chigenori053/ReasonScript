/**
 * Execution Plan Flow View — structured reasoning path visualization.
 * Specification: reasonscript-ide-runtime-visualization/0.1 §9
 */
import { useState } from "react";
import type { ExecutionPlanViewModel, ExecutionPlanStepViewModel } from "../visualization/viewModels";
import type { ArtifactSelection } from "../types";
import JsonArtifactView from "./JsonArtifactView";

const OP_COLOR: Record<string, string> = {
  function_return: "#60a5fa",
  calculation_result: "#a78bfa",
  initial_state: "#34d399",
  result_projection: "#fb923c",
  transition: "#9ca3af",
};

const OP_ICON: Record<string, string> = {
  function_return: "fn→",
  calculation_result: "calc",
  initial_state: "init",
  result_projection: "proj",
  transition: "→",
};

interface Props {
  vm: ExecutionPlanViewModel;
  rawData?: unknown;
  selectedArtifact?: ArtifactSelection | null;
  onSelectArtifact?: (sel: ArtifactSelection | null) => void;
}

function StepRow({
  step,
  isSelected,
  onSelect,
}: {
  step: ExecutionPlanStepViewModel;
  isSelected: boolean;
  onSelect: () => void;
}) {
  const color = OP_COLOR[step.operationType] ?? "#9ca3af";
  const icon = OP_ICON[step.operationType] ?? "→";

  return (
    <div
      onClick={onSelect}
      style={{
        padding: "8px 16px",
        borderBottom: "1px solid #111827",
        cursor: "pointer",
        background: isSelected ? "#1e3a5f" : "transparent",
        fontSize: 13,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <span style={{ color: "#6b7280", minWidth: 24, fontSize: 11 }}>{step.index}</span>
        <span style={{ color, fontWeight: 700, fontSize: 11, minWidth: 36 }}>{icon}</span>
        <span style={{ color: "#9ca3af", fontSize: 12 }}>{step.source}</span>
        <span style={{ color: "#6b7280" }}>→</span>
        <span style={{ color: "#e5e7eb", fontSize: 12, flex: 1 }}>{step.target}</span>
      </div>
      {step.transitionId && (
        <div style={{ color: "#374151", fontSize: 11, marginTop: 2, paddingLeft: 70 }}>
          {step.transitionId}
        </div>
      )}
    </div>
  );
}

export default function ExecutionPlanFlowView({
  vm,
  rawData,
  selectedArtifact,
  onSelectArtifact,
}: Props) {
  const [tab, setTab] = useState<"flow" | "raw">("flow");

  if (vm.status === "not_available") {
    return (
      <div style={{ padding: "12px 16px", color: "#6b7280", fontSize: 13 }}>
        Execution Plan — not available
      </div>
    );
  }

  const handleSelectStep = (step: ExecutionPlanStepViewModel) => {
    const sel: ArtifactSelection = {
      kind: "execution_plan",
      id: `ep-step-${step.stepId}`,
      label: step.stepId,
      span: null,
      navigation_mode: step.transitionId ? "symbol_fallback" : "none",
      relatedIds: step.transitionId ? [`ir-transition-${step.transitionId}`] : [],
      metadata: {
        step_id: step.stepId,
        transition_id: step.transitionId,
        source: step.source,
        target: step.target,
        symbol_fallback: step.transitionId?.split(".").pop() ?? null,
      },
    };
    onSelectArtifact?.(sel);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Summary bar */}
      <div
        style={{
          padding: "6px 16px",
          borderBottom: "1px solid #1f2937",
          fontSize: 12,
          color: "#9ca3af",
          display: "flex",
          gap: 16,
          flexShrink: 0,
          flexWrap: "wrap",
        }}
      >
        <span style={{ color: vm.reachable ? "#34d399" : "#f87171" }}>
          {vm.reachable ? "✓ Reachable" : "✕ Unreachable"}
        </span>
        {vm.goalTarget && (
          <span>goal: <strong style={{ color: "#e5e7eb" }}>{vm.goalTarget}</strong></span>
        )}
        {vm.distance != null && <span>distance: {vm.distance}</span>}
        {vm.pathSignature && (
          <span>path: <strong style={{ color: "#a78bfa" }}>{vm.pathSignature}</strong></span>
        )}
        {vm.selectedBranch && (
          <span>branch: <strong style={{ color: "#60a5fa" }}>{vm.selectedBranch}</strong></span>
        )}
        {vm.expectedCost != null && (
          <span style={{ color: "#6b7280" }}>cost: {vm.expectedCost}</span>
        )}
      </div>

      {/* Sub-tabs */}
      <div style={{ display: "flex", borderBottom: "1px solid #1f2937", flexShrink: 0 }}>
        {(["flow", "raw"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              padding: "5px 12px",
              fontSize: 12,
              background: "transparent",
              border: "none",
              borderBottom: tab === t ? "2px solid #60a5fa" : "2px solid transparent",
              color: tab === t ? "#e5e7eb" : "#6b7280",
              cursor: "pointer",
            }}
          >
            {t === "flow" ? `Steps (${vm.steps.length})` : "Raw JSON"}
          </button>
        ))}
      </div>

      <div style={{ flex: 1, overflow: "auto" }}>
        {tab === "raw" ? (
          <JsonArtifactView data={rawData} label="Execution Plan" />
        ) : vm.status === "failed" ? (
          <div style={{ padding: "16px" }}>
            <div style={{ color: "#f87171", fontSize: 13, marginBottom: 8 }}>
              Execution Plan: failed
            </div>
            {vm.failureReason && (
              <div style={{ color: "#9ca3af", fontSize: 12 }}>{vm.failureReason}</div>
            )}
          </div>
        ) : vm.steps.length === 0 ? (
          <div style={{ padding: "12px 16px", color: "#6b7280", fontSize: 13 }}>
            No steps
          </div>
        ) : (
          <>
            {vm.steps.map((step) => {
              const id = `ep-step-${step.stepId}`;
              return (
                <StepRow
                  key={id}
                  step={step}
                  isSelected={selectedArtifact?.id === id}
                  onSelect={() => handleSelectStep(step)}
                />
              );
            })}
            {vm.alternativePaths.length > 0 && (
              <div style={{ padding: "8px 16px", borderTop: "1px solid #1f2937" }}>
                <div style={{ color: "#6b7280", fontSize: 11, marginBottom: 4 }}>
                  Alternative paths: {vm.alternativePaths.length}
                </div>
                {vm.alternativePaths.map((alt, i) => (
                  <div key={i} style={{ color: "#374151", fontSize: 11, paddingLeft: 8 }}>
                    {alt.stepIds.join(" → ")}
                    {alt.cost != null && ` (cost ${alt.cost})`}
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
