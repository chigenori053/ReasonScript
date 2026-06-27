import type { ArtifactSelection } from "../types";
import JsonArtifactView from "./JsonArtifactView";

interface DepNode {
  id?: string;
  name?: string;
  symbol?: string;
  [key: string]: unknown;
}

interface DepEdge {
  from?: string;
  to?: string;
  source?: string;
  target?: string;
  [key: string]: unknown;
}

interface DepGraph {
  nodes?: DepNode[];
  edges?: DepEdge[];
  [key: string]: unknown;
}

interface Props {
  data: unknown;
  selectedArtifact?: ArtifactSelection | null;
  onSelectArtifact?: (sel: ArtifactSelection | null) => void;
}

function nodeLabel(n: DepNode): string {
  return n.name ?? n.symbol ?? n.id ?? "(node)";
}

export default function DependencyGraphView({ data, selectedArtifact, onSelectArtifact }: Props) {
  if (data == null) {
    return (
      <div style={{ padding: "12px 16px", color: "#6b7280", fontSize: 13 }}>
        Dependency graph — not available
      </div>
    );
  }

  const graph = data as DepGraph;
  const nodes = graph.nodes ?? [];
  const edges = graph.edges ?? [];

  if (nodes.length === 0 && edges.length === 0) {
    return (
      <div style={{ height: "100%", overflow: "auto" }}>
        <div style={{ padding: "8px 16px", color: "#6b7280", fontSize: 13 }}>
          No dependency data — showing raw JSON
        </div>
        <JsonArtifactView data={data} label="Dependency Graph" />
      </div>
    );
  }

  const handleNodeClick = (n: DepNode, i: number) => {
    const id = `dep-node-${n.id ?? i}`;
    const symbol = n.symbol ?? n.name ?? n.id ?? null;
    const sel: ArtifactSelection = {
      kind: "dependency",
      id,
      label: nodeLabel(n),
      span: null,
      navigation_mode: symbol ? "symbol_fallback" : "none",
      metadata: { symbol, node: n },
    };
    onSelectArtifact?.(sel);
  };

  return (
    <div style={{ height: "100%", overflow: "auto" }}>
      {nodes.length > 0 && (
        <>
          <div
            style={{
              padding: "6px 16px",
              fontSize: 11,
              color: "#6b7280",
              borderBottom: "1px solid #1f2937",
            }}
          >
            Nodes ({nodes.length})
          </div>
          {nodes.map((n, i) => {
            const id = `dep-node-${n.id ?? i}`;
            const isSelected = selectedArtifact?.id === id;
            return (
              <div
                key={id}
                onClick={() => handleNodeClick(n, i)}
                style={{
                  padding: "7px 16px",
                  borderBottom: "1px solid #111827",
                  cursor: "pointer",
                  background: isSelected ? "#1e3a5f" : "transparent",
                  fontSize: 13,
                  color: "#e5e7eb",
                }}
              >
                ◆ {nodeLabel(n)}
              </div>
            );
          })}
        </>
      )}
      {edges.length > 0 && (
        <>
          <div
            style={{
              padding: "6px 16px",
              fontSize: 11,
              color: "#6b7280",
              borderBottom: "1px solid #1f2937",
              marginTop: 8,
            }}
          >
            Edges ({edges.length})
          </div>
          {edges.map((e, i) => (
            <div
              key={i}
              style={{
                padding: "5px 16px",
                borderBottom: "1px solid #111827",
                fontSize: 12,
                color: "#9ca3af",
              }}
            >
              {e.from ?? e.source} → {e.to ?? e.target}
            </div>
          ))}
        </>
      )}
    </div>
  );
}
