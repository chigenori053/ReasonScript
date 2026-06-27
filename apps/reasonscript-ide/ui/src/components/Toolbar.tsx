import type { BuildStatus } from "../state/projectStore";

interface Props {
  buildStatus: BuildStatus;
  compilerMode: string;
  onBuild: () => void;
  onRun: () => void;
  onAnalyze: () => void;
  onExport: () => void;
  onCompilerModeChange: (mode: string) => void;
}

const statusLabel: Record<BuildStatus, string> = {
  idle: "Ready",
  building: "Building…",
  ok: "✓ OK",
  error: "✕ Error",
};

const statusColor: Record<BuildStatus, string> = {
  idle: "#6b7280",
  building: "#fbbf24",
  ok: "#34d399",
  error: "#f87171",
};

export default function Toolbar({
  buildStatus,
  compilerMode,
  onBuild,
  onRun,
  onAnalyze,
  onExport,
  onCompilerModeChange,
}: Props) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        padding: "6px 12px",
        background: "#111827",
        borderBottom: "1px solid #1f2937",
        height: 40,
        flexShrink: 0,
      }}
    >
      <span style={{ color: "#9ca3af", fontSize: 13, fontWeight: 700, marginRight: 8 }}>
        ReasonScript IDE
      </span>

      <button className="toolbar-btn" onClick={onBuild} title="⌘B">
        Build
      </button>
      <button className="toolbar-btn" onClick={onRun} title="⌘↵">
        Run
      </button>
      <button className="toolbar-btn" onClick={onAnalyze} title="⌘⇧A">
        Analyze
      </button>
      <button className="toolbar-btn secondary" onClick={onExport}>
        Export
      </button>

      <div style={{ flex: 1 }} />

      <select
        value={compilerMode}
        onChange={(e) => onCompilerModeChange(e.target.value)}
        style={{
          background: "#1f2937",
          color: "#d1d5db",
          border: "1px solid #374151",
          borderRadius: 4,
          padding: "2px 6px",
          fontSize: 12,
        }}
      >
        <option value="normal">normal</option>
        <option value="strict">strict</option>
        <option value="rust_compatible">rust_compatible</option>
      </select>

      <span
        style={{
          fontSize: 12,
          color: statusColor[buildStatus],
          minWidth: 80,
          textAlign: "right",
        }}
      >
        {statusLabel[buildStatus]}
      </span>
    </div>
  );
}
