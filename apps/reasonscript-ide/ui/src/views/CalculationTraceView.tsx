import type { RuntimeObservabilityViewModel } from "../viewModels/runtimeObservability";

export default function CalculationTraceView({
  vm,
}: {
  vm: RuntimeObservabilityViewModel;
}) {
  if (vm.calculation.status === "unavailable" || vm.calculation.status === "empty") {
    return <div className="ide-runtime-empty">No calculation details reported.</div>;
  }

  return (
    <div className="ide-runtime-section" data-calculation-trace="phase-4-5-c2-b">
      <div className="ide-section-title">Calculation Trace</div>
      {vm.calculation.items.map((item) => (
        <div className="ide-runtime-card" key={item.id}>
          <div className="ide-runtime-card-title">
            <span>{item.name ?? item.id}</span>
            {item.stepIndex != null && <strong>step {item.stepIndex}</strong>}
          </div>
          {item.expression && <div className="ide-runtime-muted">expression: {item.expression}</div>}
          {item.dependencies && item.dependencies.length > 0 && (
            <div className="ide-runtime-muted">dependencies: {item.dependencies.join(", ")}</div>
          )}
          {item.result != null && <pre className="ide-runtime-value">{String(item.result)}</pre>}
        </div>
      ))}
    </div>
  );
}
