import type { RuntimeObservabilityViewModel } from "../viewModels/runtimeObservability";

export default function RuntimeTraceView({
  vm,
}: {
  vm: RuntimeObservabilityViewModel;
}) {
  if (vm.runtimeTrace.status === "fallback") {
    return (
      <div className="ide-runtime-section" data-runtime-trace="phase-4-5-c2-b">
        <div className="ide-runtime-fallback">
          Runtime trace unavailable; showing simulation trace fallback.
        </div>
        <RuntimeTraceRows vm={vm} />
      </div>
    );
  }

  if (vm.runtimeTrace.status === "unavailable") {
    return <div className="ide-runtime-empty">Runtime trace unavailable.</div>;
  }

  if (vm.runtimeTrace.status === "empty") {
    return <div className="ide-runtime-empty">No runtime trace reported.</div>;
  }

  return (
    <div className="ide-runtime-section" data-runtime-trace="phase-4-5-c2-b">
      <div className="ide-section-title">Runtime Trace</div>
      <RuntimeTraceRows vm={vm} />
    </div>
  );
}

function RuntimeTraceRows({ vm }: { vm: RuntimeObservabilityViewModel }) {
  return (
    <>
      {vm.runtimeTrace.steps.map((step) => (
        <div className="ide-runtime-row" key={step.id}>
          <span className="ide-runtime-kind">{step.event}</span>
          <span className="ide-runtime-muted">step {step.stepIndex}</span>
          {step.operation && <span className="ide-runtime-muted">{step.operation}</span>}
          {step.source && <span className="ide-runtime-muted">{step.source}</span>}
          {step.target && <span className="ide-runtime-muted">to {step.target}</span>}
          {step.branch && <span className="ide-runtime-muted">branch {step.branch}</span>}
        </div>
      ))}
    </>
  );
}
