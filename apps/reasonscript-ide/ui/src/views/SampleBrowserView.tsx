import type { SampleBrowserViewModel, ReasonScriptSample } from "../viewModels/sampleBrowser";

interface Props {
  vm: SampleBrowserViewModel;
  selectedSampleId?: string;
  loading?: boolean;
  dirty?: boolean;
  onRefresh: () => void;
  onSelectSample: (sampleId: string) => void;
  onLoadSample: (sample: ReasonScriptSample) => void;
}

export default function SampleBrowserView({
  vm,
  selectedSampleId,
  loading,
  dirty,
  onRefresh,
  onSelectSample,
  onLoadSample,
}: Props) {
  const selected = vm.samples.find((sample) => sample.id === selectedSampleId);

  return (
    <section style={{ borderTop: "1px solid #1f2937", padding: "8px 10px" }} data-sample-browser="phase-4-5-c2-e">
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
        <span style={{ fontSize: 10, fontWeight: 700, color: "#6b7280", textTransform: "uppercase" }}>
          Examples
        </span>
        <button type="button" onClick={onRefresh} disabled={loading} title="Refresh examples" style={smallButtonStyle}>
          {loading ? "..." : "Refresh"}
        </button>
      </div>

      {vm.status === "failed" && <div style={emptyStyle}>Example loading failed.</div>}
      {vm.status === "unavailable" && vm.samples.length === 0 && <div style={emptyStyle}>Examples unavailable.</div>}
      {vm.samples.length === 0 && vm.status !== "failed" && vm.status !== "unavailable" && (
        <div style={emptyStyle}>No examples available.</div>
      )}

      {vm.samples.map((sample) => {
        const active = sample.id === selectedSampleId;
        return (
          <button
            type="button"
            key={sample.id}
            onClick={() => onSelectSample(sample.id)}
            style={{
              ...sampleRowStyle,
              background: active ? "#172554" : "transparent",
              borderColor: active ? "#1d4ed8" : "#1f2937",
            }}
          >
            <span style={{ color: "#93c5fd", fontSize: 10 }}>{sample.category ?? "sample"}</span>
            <strong>{sample.title}</strong>
            {sample.description && <span style={{ color: "#6b7280" }}>{sample.description}</span>}
          </button>
        );
      })}

      <div style={{ marginTop: 8, paddingTop: 8, borderTop: "1px solid #111827" }}>
        {!selected ? (
          <div style={emptyStyle}>No sample selected.</div>
        ) : (
          <>
            <div style={{ fontSize: 12, color: "#e5e7eb", fontWeight: 700 }}>{selected.title}</div>
            <div style={{ fontSize: 11, color: "#6b7280", marginTop: 3 }}>
              {[selected.category, selected.path, ...selected.tags].filter(Boolean).join(" / ")}
            </div>
            {!selected.source && <div style={emptyStyle}>Sample source unavailable.</div>}
            {dirty && <div style={{ ...emptyStyle, color: "#fbbf24" }}>Unsaved editor content blocks example loading.</div>}
            <button
              type="button"
              disabled={!selected.source || dirty}
              onClick={() => onLoadSample(selected)}
              style={{
                ...loadButtonStyle,
                opacity: !selected.source || dirty ? 0.45 : 1,
                cursor: !selected.source || dirty ? "not-allowed" : "pointer",
              }}
            >
              Open Example
            </button>
          </>
        )}
      </div>
    </section>
  );
}

const emptyStyle: React.CSSProperties = {
  color: "#6b7280",
  fontSize: 11,
  padding: "4px 0",
};

const smallButtonStyle: React.CSSProperties = {
  background: "#111827",
  border: "1px solid #374151",
  borderRadius: 4,
  color: "#d1d5db",
  fontSize: 11,
  padding: "2px 6px",
};

const sampleRowStyle: React.CSSProperties = {
  width: "100%",
  display: "flex",
  flexDirection: "column",
  alignItems: "flex-start",
  gap: 2,
  border: "1px solid #1f2937",
  borderRadius: 4,
  color: "#d1d5db",
  fontSize: 11,
  padding: "6px",
  marginBottom: 5,
  textAlign: "left",
};

const loadButtonStyle: React.CSSProperties = {
  marginTop: 8,
  width: "100%",
  background: "#1d4ed8",
  border: "none",
  borderRadius: 4,
  color: "#fff",
  fontSize: 12,
  padding: "5px 0",
};
