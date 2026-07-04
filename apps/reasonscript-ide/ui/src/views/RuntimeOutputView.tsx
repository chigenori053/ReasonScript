import type { RuntimeObservabilityViewModel } from "../viewModels/runtimeObservability";

export default function RuntimeOutputView({
  vm,
}: {
  vm: RuntimeObservabilityViewModel;
}) {
  if (vm.runtimeOutput.status === "unavailable" || vm.runtimeOutput.status === "empty") {
    return (
      <div className="ide-runtime-empty">
        No runtime output reported.
      </div>
    );
  }

  return (
    <div className="ide-runtime-output" data-runtime-output="phase-4-5-c2-b">
      <div className="ide-section-title">Runtime IO Output</div>
      {vm.runtimeOutput.events.map((event) => (
        <div className="ide-runtime-row" key={event.id}>
          <span className="ide-runtime-kind">{event.kind}</span>
          {event.stepIndex != null && <span className="ide-runtime-muted">step {event.stepIndex}</span>}
          {event.sourceState && <span className="ide-runtime-muted">source: {event.sourceState}</span>}
          <span className="ide-runtime-message">{event.message}</span>
        </div>
      ))}
    </div>
  );
}
