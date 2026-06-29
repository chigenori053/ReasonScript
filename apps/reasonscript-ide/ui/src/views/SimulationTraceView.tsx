/**
 * Simulation Trace View — runtime execution sequence.
 * Specification: reasonscript-ide-runtime-visualization/0.1 §10
 */
import { useState } from "react";
import type {
  SimulationTraceViewModel,
  SimulationTraceStepViewModel,
  SimulationEventType,
} from "../visualization/viewModels";
import type { ArtifactSelection } from "../types";
import JsonArtifactView from "./JsonArtifactView";

const EVENT_COLOR: Record<SimulationEventType, string> = {
  start: "#34d399",
  transition: "#60a5fa",
  branch_selection: "#a78bfa",
  calculation_result: "#fb923c",
  function_return: "#38bdf8",
  runtime_input: "#facc15",
  runtime_output: "#4ade80",
  simulation_error: "#f87171",
  unknown: "#6b7280",
};

const EVENT_LABEL: Record<SimulationEventType, string> = {
  start: "start",
  transition: "transition",
  branch_selection: "branch",
  calculation_result: "calc",
  function_return: "return",
  runtime_input: "input",
  runtime_output: "output",
  simulation_error: "error",
  unknown: "?",
};

function TraceStepRow({
  step,
  isSelected,
  onSelect,
}: {
  step: SimulationTraceStepViewModel;
  isSelected: boolean;
  onSelect: () => void;
}) {
  const color = EVENT_COLOR[step.eventType];
  const label = EVENT_LABEL[step.eventType];

  return (
    <div
      onClick={onSelect}
      style={{
        padding: "7px 16px",
        borderBottom: "1px solid #111827",
        cursor: "pointer",
        background: isSelected ? "#1e3a5f" : "transparent",
        fontSize: 13,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <span style={{ color: "#6b7280", minWidth: 24, fontSize: 11 }}>{step.index}</span>
        <span
          style={{
            color,
            fontSize: 10,
            fontWeight: 700,
            minWidth: 46,
            textAlign: "right",
            fontFamily: "monospace",
          }}
        >
          {label}
        </span>
        <span style={{ color: "#e5e7eb", flex: 1 }}>
          {step.state ?? step.transition ?? "—"}
        </span>
        {step.selectedBranch && (
          <span style={{ color: "#a78bfa", fontSize: 11 }}>→ {step.selectedBranch}</span>
        )}
        {step.emittedOutput != null && (
          <span style={{ color: "#4ade80", fontSize: 11 }}>⇒ {String(step.emittedOutput)}</span>
        )}
      </div>
      {step.condition != null && (
        <div style={{ color: "#6b7280", fontSize: 11, marginTop: 2, paddingLeft: 80 }}>
          condition: {String(step.condition)} = {String(step.conditionValue)}
        </div>
      )}
    </div>
  );
}

interface Props {
  vm: SimulationTraceViewModel;
  rawData?: unknown;
  selectedArtifact?: ArtifactSelection | null;
  onSelectArtifact?: (sel: ArtifactSelection | null) => void;
}

export default function SimulationTraceView({
  vm,
  rawData,
  selectedArtifact,
  onSelectArtifact,
}: Props) {
  const [tab, setTab] = useState<"trace" | "raw">("trace");

  if (vm.status === "not_available") {
    return (
      <div style={{ padding: "12px 16px", color: "#6b7280", fontSize: 13 }}>
        Simulation — not available
      </div>
    );
  }

  const handleSelectStep = (step: SimulationTraceStepViewModel) => {
    const sel: ArtifactSelection = {
      kind: "reason_ir",
      id: `sim-step-${step.index}`,
      label: `Step ${step.index}: ${step.eventType}`,
      span: null,
      navigation_mode: step.transition ? "symbol_fallback" : "none",
      metadata: {
        step_index: step.index,
        event_type: step.eventType,
        state: step.state,
        transition: step.transition,
        symbol_fallback: step.transition?.split(".").pop() ?? null,
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
        <span style={{ color: vm.goalReached ? "#34d399" : "#f87171" }}>
          {vm.goalReached ? "✓ Goal reached" : "✕ Goal not reached"}
        </span>
        {vm.finalState && (
          <span>final: <strong style={{ color: "#e5e7eb" }}>{vm.finalState}</strong></span>
        )}
        {vm.confidence != null && (
          <span>confidence: {(vm.confidence * 100).toFixed(0)}%</span>
        )}
        {vm.selectedBranch && (
          <span>branch: <strong style={{ color: "#a78bfa" }}>{vm.selectedBranch}</strong></span>
        )}
        {vm.pathSignature && (
          <span style={{ color: "#6b7280" }}>path: {vm.pathSignature}</span>
        )}
      </div>

      {/* Sub-tabs */}
      <div style={{ display: "flex", borderBottom: "1px solid #1f2937", flexShrink: 0 }}>
        {(["trace", "raw"] as const).map((t) => (
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
            {t === "trace" ? `Trace (${vm.steps.length})` : "Raw JSON"}
          </button>
        ))}
      </div>

      <div style={{ flex: 1, overflow: "auto" }}>
        {tab === "raw" ? (
          <JsonArtifactView data={rawData} label="Simulation" />
        ) : vm.status === "failed" ? (
          <div style={{ padding: "16px", color: "#f87171", fontSize: 13 }}>
            Simulation failed
          </div>
        ) : vm.steps.length === 0 ? (
          <div style={{ padding: "12px 16px", color: "#6b7280", fontSize: 13 }}>
            No trace steps
          </div>
        ) : (
          vm.steps.map((step) => {
            const id = `sim-step-${step.index}`;
            return (
              <TraceStepRow
                key={id}
                step={step}
                isSelected={selectedArtifact?.id === id}
                onSelect={() => handleSelectStep(step)}
              />
            );
          })
        )}
      </div>
    </div>
  );
}
