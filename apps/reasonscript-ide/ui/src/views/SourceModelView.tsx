/**
 * Source Model View — semantic structure of the source file.
 * Specification: reasonscript-ide-runtime-visualization/0.1 §7
 */
import type {
  SourceModelViewModel,
  SourceDeclarationViewModel,
  ConstructStatus,
} from "../visualization/viewModels";

const CONSTRUCT_COLOR: Record<ConstructStatus, string> = {
  preferred: "#4ade80",
  compatible: "#facc15",
  reserved: "#f87171",
};

const CONSTRUCT_LABEL: Record<ConstructStatus, string> = {
  preferred: "preferred",
  compatible: "compatible",
  reserved: "reserved",
};

const KIND_COLOR: Record<SourceDeclarationViewModel["kind"], string> = {
  function: "#60a5fa",
  calculation: "#a78bfa",
  state: "#34d399",
  goal: "#fb923c",
  constraint: "#f472b6",
  transition: "#38bdf8",
  struct: "#facc15",
  enum: "#fb923c",
  const: "#9ca3af",
  other: "#6b7280",
};

const KIND_ICON: Record<SourceDeclarationViewModel["kind"], string> = {
  function: "fn",
  calculation: "calc",
  state: "state",
  goal: "goal",
  constraint: "const",
  transition: "→",
  struct: "struct",
  enum: "enum",
  const: "const",
  other: "·",
};

interface Props {
  vm: SourceModelViewModel;
}

export default function SourceModelView({ vm }: Props) {
  if (vm.entries.length === 0) {
    return (
      <div style={{ padding: "16px", color: "#6b7280", fontSize: 13 }}>
        No top-level constructs found.
      </div>
    );
  }

  return (
    <div style={{ overflow: "auto", height: "100%" }}>
      {vm.entries.map((entry, i) => {
        const color = CONSTRUCT_COLOR[entry.status];
        const statusLabel = CONSTRUCT_LABEL[entry.status];

        return (
          <div
            key={i}
            style={{
              borderBottom: "1px solid #1f2937",
              padding: "10px 16px",
            }}
          >
            {/* Header */}
            <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 6 }}>
              <span style={{ color, fontSize: 11, fontWeight: 700, textTransform: "uppercase" }}>
                {entry.construct}
              </span>
              <span style={{ color: "#e5e7eb", fontSize: 14, fontWeight: 600 }}>
                {entry.name}
              </span>
              <span style={{ color: "#6b7280", fontSize: 11 }}>— {statusLabel}</span>
            </div>

            {/* Declarations */}
            {entry.declarations.length === 0 ? (
              <div style={{ color: "#374151", fontSize: 12, paddingLeft: 8 }}>
                (empty)
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 3, paddingLeft: 8 }}>
                {entry.declarations.map((decl, j) => {
                  const kColor = KIND_COLOR[decl.kind];
                  const kIcon = KIND_ICON[decl.kind];
                  return (
                    <div key={j} style={{ display: "flex", alignItems: "baseline", gap: 8, fontSize: 12 }}>
                      <span
                        style={{
                          color: kColor,
                          fontSize: 10,
                          fontWeight: 700,
                          minWidth: 36,
                          textAlign: "right",
                          fontFamily: "monospace",
                        }}
                      >
                        {kIcon}
                      </span>
                      <span style={{ color: "#d1d5db" }}>{decl.name}</span>
                      {decl.signature && (
                        <span style={{ color: "#6b7280", fontSize: 11 }}>{decl.signature}</span>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
