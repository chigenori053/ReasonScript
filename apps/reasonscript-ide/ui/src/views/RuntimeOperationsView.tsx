/**
 * Runtime Operations View — external runtime calls (print, search, plan, etc.)
 * Specification: reasonscript-ide-runtime-visualization/0.1 §13
 */
import type { SimulationTraceViewModel } from "../visualization/viewModels";

const OP_COLOR: Record<string, string> = {
  runtime_output: "#4ade80",
  runtime_input: "#facc15",
  start: "#34d399",
  unknown: "#6b7280",
};

interface Props {
  simulationVm: SimulationTraceViewModel;
}

export default function RuntimeOperationsView({ simulationVm }: Props) {
  const runtimeSteps = simulationVm.steps.filter(
    (s) => s.eventType === "runtime_output" || s.eventType === "runtime_input"
  );

  if (simulationVm.status === "unavailable") {
    return (
      <div style={{ padding: "12px 16px", color: "#6b7280", fontSize: 13 }}>
        Runtime Operations — not available (run simulation first)
      </div>
    );
  }

  if (runtimeSteps.length === 0) {
    return (
      <div style={{ padding: "12px 16px", color: "#6b7280", fontSize: 13 }}>
        No runtime operations in this execution.
      </div>
    );
  }

  return (
    <div style={{ overflow: "auto", height: "100%" }}>
      {runtimeSteps.map((step, i) => {
        const color = OP_COLOR[step.eventType] ?? "#9ca3af";
        const raw = step.raw as Record<string, unknown> | undefined;
        const opName = (raw?.operation as string) ?? step.eventType;

        return (
          <div
            key={i}
            style={{
              padding: "10px 16px",
              borderBottom: "1px solid #111827",
              fontSize: 13,
            }}
          >
            <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 4 }}>
              <span style={{ color, fontWeight: 700, minWidth: 70 }}>{opName}</span>
              {step.state && (
                <span style={{ color: "#9ca3af", fontSize: 12 }}>
                  source: {step.state}
                </span>
              )}
              <span
                style={{
                  color: step.eventType === "runtime_output" ? "#34d399" : "#facc15",
                  fontSize: 11,
                  marginLeft: "auto",
                }}
              >
                {step.eventType === "runtime_output" ? "output" : "input"}
              </span>
            </div>

            {step.emittedOutput != null && (
              <div style={{ color: "#4ade80", fontSize: 12, paddingLeft: 78 }}>
                ⇒ {String(step.emittedOutput)}
              </div>
            )}

            {step.transition && (
              <div style={{ color: "#374151", fontSize: 11, paddingLeft: 78 }}>
                via: {step.transition}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
