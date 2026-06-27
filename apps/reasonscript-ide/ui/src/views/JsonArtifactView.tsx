interface Props {
  data: unknown;
  label: string;
  onSelectNode?: (node: unknown) => void;
}

export default function JsonArtifactView({ data, label }: Props) {
  if (data == null) {
    return (
      <div style={{ padding: "12px 16px", color: "#6b7280", fontSize: 13 }}>
        {label} — not available
      </div>
    );
  }

  return (
    <div style={{ height: "100%", overflow: "auto" }}>
      <pre
        style={{
          margin: 0,
          padding: "12px 16px",
          fontSize: 12,
          color: "#d1d5db",
          fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
        }}
      >
        {JSON.stringify(data, null, 2)}
      </pre>
    </div>
  );
}
