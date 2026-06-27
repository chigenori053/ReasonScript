import { useState } from "react";
import type { ReasonIR, ReasonIRTransition, ArtifactSelection } from "../types";
import JsonArtifactView from "./JsonArtifactView";

interface Props {
  data: unknown;
  selectedArtifact?: ArtifactSelection | null;
  onSelectArtifact?: (sel: ArtifactSelection | null) => void;
}

function transitionLabel(t: ReasonIRTransition): string {
  if (t.transition_id) return t.transition_id;
  if (t.effect?.function) return t.effect.function;
  return "(unknown)";
}

function TransitionRow({
  t,
  index,
  isSelected,
  onSelect,
}: {
  t: ReasonIRTransition;
  index: number;
  isSelected: boolean;
  onSelect: (t: ReasonIRTransition, index: number) => void;
}) {
  const label = transitionLabel(t);
  const fn = t.effect?.function ?? "";
  const returnPath = t.effect?.return_path ?? "";

  return (
    <div
      onClick={() => onSelect(t, index)}
      style={{
        padding: "7px 16px",
        borderBottom: "1px solid #111827",
        cursor: "pointer",
        background: isSelected ? "#1e3a5f" : "transparent",
        fontSize: 13,
        display: "flex",
        gap: 12,
        alignItems: "center",
      }}
    >
      <span style={{ color: "#60a5fa", fontWeight: 600, minWidth: 16 }}>→</span>
      <span style={{ color: "#e5e7eb", flex: 1 }}>{label}</span>
      {fn && <span style={{ color: "#9ca3af", fontSize: 11 }}>{fn}</span>}
      {returnPath && <span style={{ color: "#374151", fontSize: 11 }}>{returnPath}</span>}
      <span style={{ color: "#1f2937", fontSize: 10 }}>
        {t.transition_id ? "🔗" : "no span"}
      </span>
    </div>
  );
}

export default function ReasonIRView({ data, selectedArtifact, onSelectArtifact }: Props) {
  const [tab, setTab] = useState<"transitions" | "raw">("transitions");

  if (data == null) {
    return (
      <div style={{ padding: "12px 16px", color: "#6b7280", fontSize: 13 }}>
        Reason IR — not available
      </div>
    );
  }

  const ir = data as ReasonIR;
  const transitions = ir.transitions ?? [];

  const handleSelectTransition = (t: ReasonIRTransition, index: number) => {
    const id = `ir-transition-${t.transition_id ?? index}`;
    const symbolFallback = t.effect?.function?.split(".").pop()
      ?? t.transition_id?.split(".").pop()
      ?? null;

    const sel: ArtifactSelection = {
      kind: "reason_ir",
      id,
      label: transitionLabel(t),
      span: null, // Reason IR has no span yet — use symbol fallback
      navigation_mode: symbolFallback ? "symbol_fallback" : "none",
      metadata: {
        transition_id: t.transition_id,
        function: t.effect?.function,
        return_path: t.effect?.return_path,
        symbol_fallback: symbolFallback,
      },
    };
    onSelectArtifact?.(sel);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Sub-tab bar */}
      <div style={{ display: "flex", borderBottom: "1px solid #1f2937", flexShrink: 0 }}>
        {(["transitions", "raw"] as const).map((t) => (
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
            {t === "transitions" ? `Transitions (${transitions.length})` : "Raw JSON"}
          </button>
        ))}
      </div>

      <div style={{ flex: 1, overflow: "auto" }}>
        {tab === "transitions" ? (
          transitions.length === 0 ? (
            <div style={{ padding: "12px 16px", color: "#6b7280", fontSize: 13 }}>
              No transitions
            </div>
          ) : (
            transitions.map((t, i) => {
              const id = `ir-transition-${t.transition_id ?? i}`;
              return (
                <TransitionRow
                  key={id}
                  t={t}
                  index={i}
                  isSelected={selectedArtifact?.id === id}
                  onSelect={handleSelectTransition}
                />
              );
            })
          )
        ) : (
          <JsonArtifactView data={data} label="Reason IR" />
        )}
      </div>
    </div>
  );
}
