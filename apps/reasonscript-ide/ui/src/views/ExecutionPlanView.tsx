import { useState } from "react";
import type {
  ExecutionPlan, ExecutionPlanStep, ReasonIR, ReasonIRTransition,
  ArtifactSelection,
} from "../types";
import JsonArtifactView from "./JsonArtifactView";

interface Props {
  data: unknown;
  reasonIr?: unknown;
  selectedArtifact?: ArtifactSelection | null;
  onSelectArtifact?: (sel: ArtifactSelection | null) => void;
}

function resolveTransition(
  transitionId: string | undefined,
  ir: ReasonIR | null
): ReasonIRTransition | null {
  if (!transitionId || !ir?.transitions) return null;
  return ir.transitions.find((t) => t.transition_id === transitionId) ?? null;
}

function symbolFromTransition(t: ReasonIRTransition | null): string | null {
  if (!t) return null;
  return t.effect?.function?.split(".").pop()
    ?? t.transition_id?.split(".").pop()
    ?? null;
}

export default function ExecutionPlanView({
  data,
  reasonIr,
  selectedArtifact,
  onSelectArtifact,
}: Props) {
  const [tab, setTab] = useState<"steps" | "raw">("steps");

  if (data == null) {
    return (
      <div style={{ padding: "12px 16px", color: "#6b7280", fontSize: 13 }}>
        Execution Plan — not available
      </div>
    );
  }

  const plan = data as ExecutionPlan;
  const ir = (reasonIr ?? null) as ReasonIR | null;
  const steps = plan.selected_steps ?? [];

  const handleSelectStep = (step: ExecutionPlanStep, index: number) => {
    const id = `ep-step-${step.step_id ?? index}`;
    const transition = resolveTransition(step.transition_id, ir);
    const symbol = symbolFromTransition(transition);

    const sel: ArtifactSelection = {
      kind: "execution_plan",
      id,
      label: step.step_id ?? `step-${index}`,
      span: null, // ExecutionPlan has no span; resolve via transition → symbol
      navigation_mode: symbol ? "symbol_fallback" : "none",
      relatedIds: step.transition_id ? [`ir-transition-${step.transition_id}`] : [],
      metadata: {
        step_id: step.step_id,
        transition_id: step.transition_id,
        source: step.source,
        target: step.target,
        symbol_fallback: symbol,
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
        }}
      >
        {plan.reachable != null && (
          <span style={{ color: plan.reachable ? "#34d399" : "#f87171" }}>
            {plan.reachable ? "✓ Reachable" : "✕ Unreachable"}
          </span>
        )}
        {plan.path_signature && (
          <span>path: <strong style={{ color: "#e5e7eb" }}>{plan.path_signature}</strong></span>
        )}
        {plan.distance != null && <span>distance: {plan.distance}</span>}
      </div>

      {/* Sub-tab bar */}
      <div style={{ display: "flex", borderBottom: "1px solid #1f2937", flexShrink: 0 }}>
        {(["steps", "raw"] as const).map((t) => (
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
            {t === "steps" ? `Steps (${steps.length})` : "Raw JSON"}
          </button>
        ))}
      </div>

      <div style={{ flex: 1, overflow: "auto" }}>
        {tab === "steps" ? (
          steps.length === 0 ? (
            <div style={{ padding: "12px 16px", color: "#6b7280", fontSize: 13 }}>
              No selected steps
            </div>
          ) : (
            steps.map((step, i) => {
              const id = `ep-step-${step.step_id ?? i}`;
              const isSelected = selectedArtifact?.id === id;
              const transition = resolveTransition(step.transition_id, ir);
              const symbol = symbolFromTransition(transition);

              return (
                <div
                  key={id}
                  onClick={() => handleSelectStep(step, i)}
                  style={{
                    padding: "8px 16px",
                    borderBottom: "1px solid #111827",
                    cursor: "pointer",
                    background: isSelected ? "#1e3a5f" : "transparent",
                    fontSize: 13,
                  }}
                >
                  <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
                    <span style={{ color: "#6366f1", minWidth: 60 }}>
                      {step.step_id ?? `step-${i}`}
                    </span>
                    <span style={{ color: "#9ca3af", fontSize: 11 }}>
                      {step.source} → {step.target}
                    </span>
                    {symbol && (
                      <span style={{ color: "#60a5fa", fontSize: 11, marginLeft: "auto" }}>
                        ↗ {symbol}
                      </span>
                    )}
                  </div>
                  {step.transition_id && (
                    <div style={{ color: "#374151", fontSize: 11, marginTop: 2 }}>
                      transition: {step.transition_id}
                    </div>
                  )}
                </div>
              );
            })
          )
        ) : (
          <JsonArtifactView data={data} label="Execution Plan" />
        )}
      </div>
    </div>
  );
}
