import { useState, useCallback } from "react";
import type { FileNode, FileNodeKind, WorkspaceState } from "../types";
import { openWorkspace, refreshWorkspace } from "../bridge";

// ---------------------------------------------------------------------------
// Icon helpers
// ---------------------------------------------------------------------------

function fileIcon(kind: FileNodeKind, extension?: string | null, expanded?: boolean): string {
  if (kind === "directory") return expanded ? "▾" : "▸";
  if (kind === "symlink") return "↗";
  const ext = extension ?? "";
  switch (ext) {
    case "rsn": return "◈";
    case "rs": return "⚙";
    case "py": return "»";
    case "ts": case "tsx": return "◻";
    case "json": return "{}";
    case "toml": return "⚙";
    case "md": return "§";
    default: return "·";
  }
}

// ---------------------------------------------------------------------------
// Tree Node
// ---------------------------------------------------------------------------

interface NodeProps {
  node: FileNode;
  depth: number;
  selectedPath: string | null;
  expandedPaths: Set<string>;
  onSelect: (path: string) => void;
  onToggle: (path: string) => void;
}

function TreeNode({ node, depth, selectedPath, expandedPaths, onSelect, onToggle }: NodeProps) {
  const isDir = node.kind === "directory";
  const isExpanded = expandedPaths.has(node.path);
  const isSelected = selectedPath === node.path;
  const ignored = node.is_ignored;

  const handleClick = () => {
    if (isDir) {
      if (!ignored) onToggle(node.path);
    } else {
      if (!ignored) onSelect(node.path);
    }
  };

  return (
    <>
      <div
        onClick={handleClick}
        style={{
          display: "flex",
          alignItems: "center",
          paddingLeft: 10 + depth * 14,
          paddingTop: 3,
          paddingBottom: 3,
          paddingRight: 8,
          fontSize: 12,
          cursor: ignored ? "default" : "pointer",
          background: isSelected ? "#1e3a5f" : "transparent",
          color: ignored ? "#2d3748" : isDir ? "#c4b5fd" : "#d1d5db",
          userSelect: "none",
          transition: "background 0.1s",
        }}
        onMouseEnter={(e) => {
          if (!isSelected && !ignored)
            (e.currentTarget as HTMLElement).style.background = "#1a2234";
        }}
        onMouseLeave={(e) => {
          if (!isSelected)
            (e.currentTarget as HTMLElement).style.background = "transparent";
        }}
      >
        <span style={{ marginRight: 5, fontSize: 10, minWidth: 12, color: isDir ? "#7c3aed" : "#4b5563" }}>
          {fileIcon(node.kind, node.extension, isExpanded)}
        </span>
        <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {node.name}
        </span>
      </div>

      {isDir && isExpanded && !ignored && node.children.map((child) => (
        <TreeNode
          key={child.path}
          node={child}
          depth={depth + 1}
          selectedPath={selectedPath}
          expandedPaths={expandedPaths}
          onSelect={onSelect}
          onToggle={onToggle}
        />
      ))}
    </>
  );
}

// ---------------------------------------------------------------------------
// Open Workspace input
// ---------------------------------------------------------------------------

function OpenBar({ onOpen, loading }: { onOpen: (path: string) => void; loading: boolean }) {
  const [input, setInput] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = input.trim();
    if (trimmed) onOpen(trimmed);
  };

  return (
    <form onSubmit={handleSubmit} style={{ padding: "8px" }}>
      <div style={{ fontSize: 11, color: "#6b7280", marginBottom: 6 }}>
        Open a local directory as workspace
      </div>
      <input
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder="/path/to/project"
        disabled={loading}
        style={{
          width: "100%",
          boxSizing: "border-box",
          background: "#111827",
          border: "1px solid #374151",
          borderRadius: 4,
          color: "#e5e7eb",
          fontSize: 12,
          padding: "4px 8px",
          outline: "none",
          marginBottom: 6,
        }}
      />
      <button
        type="submit"
        disabled={loading || !input.trim()}
        style={{
          width: "100%",
          background: "#1d4ed8",
          border: "none",
          borderRadius: 4,
          color: "#fff",
          fontSize: 12,
          padding: "5px 0",
          cursor: loading || !input.trim() ? "not-allowed" : "pointer",
          opacity: !input.trim() ? 0.5 : 1,
        }}
      >
        {loading ? "Opening…" : "Open Workspace"}
      </button>
    </form>
  );
}

// ---------------------------------------------------------------------------
// Main view
// ---------------------------------------------------------------------------

export interface WorkspaceExplorerProps {
  workspace: WorkspaceState | null;
  selectedPath: string | null;
  expandedPaths: Set<string>;
  onSetWorkspace: (ws: WorkspaceState | null) => void;
  onSelectPath: (path: string | null) => void;
  onToggleExpanded: (path: string) => void;
  onClearWorkspace: () => void;
}

export default function WorkspaceExplorerView({
  workspace,
  selectedPath,
  expandedPaths,
  onSetWorkspace,
  onSelectPath,
  onToggleExpanded,
  onClearWorkspace,
}: WorkspaceExplorerProps) {
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleOpen = useCallback(
    async (path: string) => {
      setLoading(true);
      setError(null);
      try {
        const ws = await openWorkspace(path);
        onSetWorkspace(ws);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setLoading(false);
      }
    },
    [onSetWorkspace]
  );

  const handleRefresh = useCallback(async () => {
    if (!workspace) return;
    setLoading(true);
    setError(null);
    try {
      const ws = await refreshWorkspace(workspace.root_path);
      onSetWorkspace(ws);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [workspace, onSetWorkspace]);

  return (
    <div
      style={{
        width: 240,
        minWidth: 200,
        display: "flex",
        flexDirection: "column",
        borderRight: "1px solid #1f2937",
        background: "#090d17",
        overflow: "hidden",
        flexShrink: 0,
      }}
    >
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "6px 10px",
          borderBottom: "1px solid #1f2937",
          flexShrink: 0,
        }}
      >
        <span
          style={{
            fontSize: 10,
            fontWeight: 700,
            color: "#4b5563",
            letterSpacing: "0.08em",
            textTransform: "uppercase",
          }}
        >
          Explorer
        </span>
        {workspace && (
          <div style={{ display: "flex", gap: 2 }}>
            <button
              onClick={handleRefresh}
              disabled={loading}
              title="Refresh"
              style={iconBtnStyle}
            >
              ↻
            </button>
            <button
              onClick={onClearWorkspace}
              title="Close workspace"
              style={iconBtnStyle}
            >
              ✕
            </button>
          </div>
        )}
      </div>

      {/* Workspace root name */}
      {workspace && (
        <div
          title={workspace.root_path}
          style={{
            padding: "5px 10px",
            fontSize: 12,
            fontWeight: 700,
            color: "#a5b4fc",
            borderBottom: "1px solid #1f2937",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
            flexShrink: 0,
          }}
        >
          {workspace.root_name}
        </div>
      )}

      {/* Scan partial warning */}
      {workspace?.scan_status === "partial" && (
        <div
          style={{
            padding: "4px 10px",
            fontSize: 11,
            color: "#fbbf24",
            background: "#451a03",
            borderBottom: "1px solid #78350f",
            flexShrink: 0,
          }}
        >
          ⚠ Scan truncated (file limit reached)
        </div>
      )}

      {/* Error */}
      {error && (
        <div
          style={{
            padding: "6px 10px",
            fontSize: 11,
            color: "#f87171",
            background: "#450a0a",
            borderBottom: "1px solid #7f1d1d",
            flexShrink: 0,
            wordBreak: "break-word",
          }}
        >
          {error}
        </div>
      )}

      {/* Content */}
      <div style={{ flex: 1, overflow: "auto" }}>
        {!workspace ? (
          <OpenBar onOpen={handleOpen} loading={loading} />
        ) : (
          <>
            {workspace.files.map((node) => (
              <TreeNode
                key={node.path}
                node={node}
                depth={0}
                selectedPath={selectedPath}
                expandedPaths={expandedPaths}
                onSelect={onSelectPath}
                onToggle={onToggleExpanded}
              />
            ))}
            {workspace.files.length === 0 && (
              <div style={{ padding: "12px 10px", fontSize: 12, color: "#6b7280" }}>
                Empty workspace
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

const iconBtnStyle: React.CSSProperties = {
  background: "transparent",
  border: "none",
  color: "#6b7280",
  cursor: "pointer",
  fontSize: 14,
  lineHeight: 1,
  padding: "2px 4px",
  borderRadius: 3,
};
