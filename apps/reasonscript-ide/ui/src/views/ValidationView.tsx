import type { PlatformDiagnostic, ArtifactSelection } from "../types";

interface ValidationNode {
  name: string;
  ok: boolean;
  children?: ValidationNode[];
  details?: unknown;
}

interface ValidationReport {
  ok: boolean;
  errors?: Array<{ phase: string; message: string; line?: number }>;
  tree?: ValidationNode;
}

interface Props {
  data: unknown;
  diagnostics?: PlatformDiagnostic[];
  selectedArtifact?: ArtifactSelection | null;
  onSelectArtifact?: (sel: ArtifactSelection | null) => void;
}

function findRelatedDiagnostic(
  message: string,
  diagnostics: PlatformDiagnostic[]
): PlatformDiagnostic | null {
  // Match by message substring
  return diagnostics.find(
    (d) => d.message && message && d.message.includes(message.slice(0, 30))
  ) ?? null;
}

function NodeRow({
  node,
  depth = 0,
  diagnostics,
  onSelectArtifact,
}: {
  node: ValidationNode;
  depth?: number;
  diagnostics: PlatformDiagnostic[];
  onSelectArtifact?: (sel: ArtifactSelection | null) => void;
}) {
  return (
    <>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "4px 16px",
          paddingLeft: 16 + depth * 20,
          fontSize: 13,
          borderBottom: "1px solid #111827",
        }}
      >
        <span style={{ color: node.ok ? "#34d399" : "#f87171", fontWeight: 600, minWidth: 14 }}>
          {node.ok ? "✓" : "✕"}
        </span>
        <span style={{ color: "#e5e7eb" }}>{node.name}</span>
      </div>
      {node.children?.map((c, i) => (
        <NodeRow
          key={i}
          node={c}
          depth={depth + 1}
          diagnostics={diagnostics}
          onSelectArtifact={onSelectArtifact}
        />
      ))}
    </>
  );
}

export default function ValidationView({
  data,
  diagnostics = [],
  selectedArtifact,
  onSelectArtifact,
}: Props) {
  if (data == null) {
    return (
      <div style={{ padding: "12px 16px", color: "#6b7280", fontSize: 13 }}>
        Validation — not available
      </div>
    );
  }

  const report = data as ValidationReport;

  const handleErrorClick = (msg: string, idx: number) => {
    const related = findRelatedDiagnostic(msg, diagnostics);
    const id = `validation-error-${idx}`;
    const sel: ArtifactSelection = {
      kind: "validation",
      id,
      label: msg,
      span: related?.span ?? null,
      navigation_mode: related?.span ? "span" : "none",
      relatedIds: related ? [`diag-${diagnostics.indexOf(related)}`] : [],
      metadata: { message: msg },
    };
    onSelectArtifact?.(sel);
  };

  return (
    <div style={{ height: "100%", overflow: "auto" }}>
      <div
        style={{
          padding: "8px 16px",
          background: report.ok ? "#064e3b" : "#450a0a",
          color: report.ok ? "#34d399" : "#f87171",
          fontWeight: 700,
          fontSize: 13,
          borderBottom: "1px solid #1f2937",
        }}
      >
        {report.ok ? "✓ Validation passed" : "✕ Validation failed"}
      </div>
      {report.tree && (
        <NodeRow
          node={report.tree}
          diagnostics={diagnostics}
          onSelectArtifact={onSelectArtifact}
        />
      )}
      {report.errors && report.errors.length > 0 && (
        <div style={{ padding: "8px 0" }}>
          {report.errors.map((e, i) => {
            const id = `validation-error-${i}`;
            const isSelected = selectedArtifact?.id === id;
            return (
              <div
                key={i}
                onClick={() => handleErrorClick(e.message, i)}
                style={{
                  padding: "6px 16px",
                  fontSize: 12,
                  color: "#f87171",
                  borderBottom: "1px solid #111827",
                  cursor: "pointer",
                  background: isSelected ? "#1e3a5f" : "transparent",
                }}
              >
                [{e.phase}]{e.line ? ` L${e.line}:` : ""} {e.message}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
