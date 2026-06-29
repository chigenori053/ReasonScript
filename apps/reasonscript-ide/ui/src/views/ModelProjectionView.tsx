/**
 * L7 Developer Projection View — construct status display.
 *
 * Specification: reasonscript-ide-compatibility/0.6-D §12
 *
 * Shows each top-level construct in the source with its status:
 *   - model  → active preferred syntax  (v0.6-C)
 *   - module → active compatible syntax (v0.6-B)
 *   - world / system / component → reserved (LL-002)
 */

interface TopLevelProjection {
  name: string;
  construct: string;
  status: "active-preferred" | "active-compatible" | "reserved";
  line: number;
}

const STATUS_LABEL: Record<TopLevelProjection["status"], string> = {
  "active-preferred": "active preferred syntax",
  "active-compatible": "active compatible syntax",
  reserved: "reserved top-level construct",
};

const STATUS_RECOMMENDATION: Partial<Record<TopLevelProjection["status"], string>> = {
  "active-compatible": "prefer model for new code",
};

const STATUS_DIAGNOSTIC: Partial<Record<TopLevelProjection["status"], string>> = {
  reserved: "LL-002-RESERVED-TOP-LEVEL-CONSTRUCT",
};

const STATUS_COLOR: Record<TopLevelProjection["status"], string> = {
  "active-preferred": "#4ade80",   // green-400
  "active-compatible": "#facc15",  // yellow-400
  reserved: "#f87171",             // red-400
};

const TOP_LEVEL_PATTERN =
  /^\s*(?:(?:pub|export)\s+)?(model|module|world|system|component)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{/;

function classifyConstruct(keyword: string): TopLevelProjection["status"] {
  if (keyword === "model") return "active-preferred";
  if (keyword === "module") return "active-compatible";
  return "reserved";
}

function scanProjections(source: string): TopLevelProjection[] {
  const result: TopLevelProjection[] = [];
  source.split("\n").forEach((raw, idx) => {
    const line = raw.split("//")[0];
    const match = TOP_LEVEL_PATTERN.exec(line);
    if (match) {
      result.push({
        construct: match[1],
        name: match[2],
        status: classifyConstruct(match[1]),
        line: idx + 1,
      });
    }
  });
  return result;
}

interface ModelProjectionViewProps {
  source: string;
}

export default function ModelProjectionView({ source }: ModelProjectionViewProps) {
  const projections = scanProjections(source);

  if (projections.length === 0) {
    return (
      <div style={{ padding: "16px", color: "#6b7280", fontSize: 13 }}>
        No top-level constructs found.
      </div>
    );
  }

  return (
    <div style={{ padding: "12px 16px", fontFamily: "monospace", fontSize: 13 }}>
      {projections.map((proj, i) => {
        const color = STATUS_COLOR[proj.status];
        const recommendation = STATUS_RECOMMENDATION[proj.status];
        const diagnostic = STATUS_DIAGNOSTIC[proj.status];
        return (
          <div
            key={i}
            style={{
              marginBottom: 12,
              padding: "10px 12px",
              background: "#1e1e2e",
              borderRadius: 6,
              borderLeft: `3px solid ${color}`,
            }}
          >
            <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
              <span style={{ color, fontWeight: 600 }}>{proj.construct}</span>
              <span style={{ color: "#e5e7eb" }}>{proj.name}</span>
              <span style={{ color: "#6b7280", fontSize: 11 }}>line {proj.line}</span>
            </div>
            <div style={{ marginTop: 4, color: "#9ca3af", fontSize: 12 }}>
              Status: {STATUS_LABEL[proj.status]}
            </div>
            {recommendation && (
              <div style={{ marginTop: 2, color: "#facc15", fontSize: 12 }}>
                Recommendation: {recommendation}
              </div>
            )}
            {diagnostic && (
              <div style={{ marginTop: 2, color: "#f87171", fontSize: 12 }}>
                Diagnostic: {diagnostic}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
