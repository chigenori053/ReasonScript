import type { PlatformDiagnostic, ArtifactSelection } from "../types";

interface Props {
  diagnostics: PlatformDiagnostic[];
  selectedArtifact?: ArtifactSelection | null;
  onSelectArtifact?: (sel: ArtifactSelection | null) => void;
}

const severityIcon: Record<string, string> = {
  error: "✕",
  warning: "⚠",
  hint: "💡",
  info: "ℹ",
};

const severityColor: Record<string, string> = {
  error: "#f87171",
  warning: "#fbbf24",
  hint: "#a78bfa",
  info: "#60a5fa",
};

export default function DiagnosticsView({
  diagnostics,
  selectedArtifact,
  onSelectArtifact,
}: Props) {
  if (diagnostics.length === 0) {
    return (
      <div style={{ padding: "12px 16px", color: "#6b7280", fontSize: 13 }}>
        No diagnostics
      </div>
    );
  }

  return (
    <div style={{ overflow: "auto", height: "100%" }}>
      {diagnostics.map((d, i) => {
        const id = `diag-${i}`;
        const isSelected = selectedArtifact?.id === id;
        const color = severityColor[d.severity] ?? "#9ca3af";
        const icon = severityIcon[d.severity] ?? "·";
        const line = d.span?.start_line;
        const col = d.span?.start_column;
        const locationLabel = line != null ? `${line + 1}:${(col ?? 0) + 1}` : null;
        const hasSpan = line != null;

        const handleClick = () => {
          const sel: ArtifactSelection = {
            kind: "diagnostic",
            id,
            label: d.message,
            span: d.span ?? null,
            navigation_mode: hasSpan ? "span" : "none",
            metadata: { phase: d.phase, code: d.code },
          };
          onSelectArtifact?.(sel);
        };

        return (
          <div
            key={i}
            onClick={handleClick}
            style={{
              display: "flex",
              gap: 10,
              padding: "8px 16px",
              borderBottom: "1px solid #1f2937",
              cursor: "pointer",
              fontSize: 13,
              background: isSelected ? "#1e3a5f" : "transparent",
            }}
          >
            <span style={{ color, minWidth: 14, fontWeight: 600 }}>{icon}</span>
            <span style={{ color: "#9ca3af", minWidth: 80 }}>[{d.phase}]</span>
            {d.code && (
              <span style={{ color: "#6366f1", minWidth: 80 }}>{d.code}</span>
            )}
            {locationLabel && (
              <span style={{ color: "#6b7280", minWidth: 60 }}>{locationLabel}</span>
            )}
            <span style={{ color: "#e5e7eb", flex: 1 }}>{d.message}</span>
            {!hasSpan && (
              <span style={{ color: "#374151", fontSize: 11 }}>no span</span>
            )}
          </div>
        );
      })}
    </div>
  );
}
