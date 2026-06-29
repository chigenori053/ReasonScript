/**
 * Knowledge Evidence View — generated knowledge with evidence paths.
 * Specification: reasonscript-ide-runtime-visualization/0.1 §11
 */
import { useState } from "react";
import type { KnowledgeViewModel, KnowledgeEvidenceViewModel } from "../visualization/viewModels";
import type { ArtifactSelection } from "../types";
import JsonArtifactView from "./JsonArtifactView";

function EvidenceCard({
  item,
  isSelected,
  onSelect,
}: {
  item: KnowledgeEvidenceViewModel;
  isSelected: boolean;
  onSelect: () => void;
}) {
  const confidence = item.confidence != null
    ? `${(item.confidence * 100).toFixed(0)}%`
    : null;

  return (
    <div
      onClick={onSelect}
      style={{
        padding: "10px 16px",
        borderBottom: "1px solid #111827",
        cursor: "pointer",
        background: isSelected ? "#1e3a5f" : "transparent",
        fontSize: 13,
      }}
    >
      {/* Header */}
      <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 4 }}>
        <span style={{ color: "#6b7280", fontSize: 11, minWidth: 36 }}>{item.id}</span>
        <span style={{ color: "#e5e7eb" }}>{item.source}</span>
        <span style={{ color: "#374151" }}>—{item.relation}→</span>
        <span style={{ color: "#60a5fa" }}>{item.target}</span>
        {confidence && (
          <span style={{ color: "#34d399", fontSize: 11, marginLeft: "auto" }}>
            {confidence}
          </span>
        )}
      </div>

      {/* Evidence path */}
      {item.evidencePath.length > 0 && (
        <div style={{ display: "flex", gap: 4, alignItems: "center", marginTop: 4, flexWrap: "wrap" }}>
          <span style={{ color: "#6b7280", fontSize: 11 }}>path:</span>
          {item.evidencePath.map((p, i) => (
            <span key={i} style={{ color: "#a78bfa", fontSize: 11 }}>
              {i > 0 && <span style={{ color: "#374151", marginRight: 4 }}>→</span>}
              {p}
            </span>
          ))}
        </div>
      )}

      {/* Path signature */}
      {item.pathSignature && (
        <div style={{ color: "#374151", fontSize: 11, marginTop: 2 }}>
          signature: {item.pathSignature}
        </div>
      )}

      {/* Transitions */}
      {item.transitions.length > 0 && (
        <div style={{ color: "#1f2937", fontSize: 11, marginTop: 2 }}>
          via: {item.transitions.join(", ")}
        </div>
      )}
    </div>
  );
}

interface Props {
  vm: KnowledgeViewModel;
  rawData?: unknown;
  selectedArtifact?: ArtifactSelection | null;
  onSelectArtifact?: (sel: ArtifactSelection | null) => void;
}

export default function KnowledgeEvidenceView({
  vm,
  rawData,
  selectedArtifact,
  onSelectArtifact,
}: Props) {
  const [tab, setTab] = useState<"evidence" | "raw">("evidence");

  if (vm.status === "not_available") {
    return (
      <div style={{ padding: "12px 16px", color: "#6b7280", fontSize: 13 }}>
        Knowledge — not available
      </div>
    );
  }

  const handleSelectItem = (item: KnowledgeEvidenceViewModel) => {
    const sel: ArtifactSelection = {
      kind: "reason_ir",
      id: `knowledge-${item.id}`,
      label: `${item.source} → ${item.target}`,
      span: null,
      navigation_mode: "none",
      metadata: {
        knowledge_id: item.id,
        source: item.source,
        target: item.target,
        path_signature: item.pathSignature,
        confidence: item.confidence,
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
        <span>{vm.knowledgeCount} knowledge item(s)</span>
        <span>{vm.evidenceCount} evidence item(s)</span>
      </div>

      {/* Sub-tabs */}
      <div style={{ display: "flex", borderBottom: "1px solid #1f2937", flexShrink: 0 }}>
        {(["evidence", "raw"] as const).map((t) => (
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
            {t === "evidence" ? `Items (${vm.items.length})` : "Raw JSON"}
          </button>
        ))}
      </div>

      <div style={{ flex: 1, overflow: "auto" }}>
        {tab === "raw" ? (
          <JsonArtifactView data={rawData} label="Knowledge" />
        ) : vm.status === "empty" || vm.items.length === 0 ? (
          <div style={{ padding: "12px 16px", color: "#6b7280", fontSize: 13 }}>
            No knowledge items generated
          </div>
        ) : (
          vm.items.map((item) => {
            const id = `knowledge-${item.id}`;
            return (
              <EvidenceCard
                key={id}
                item={item}
                isSelected={selectedArtifact?.id === id}
                onSelect={() => handleSelectItem(item)}
              />
            );
          })
        )}
      </div>
    </div>
  );
}
