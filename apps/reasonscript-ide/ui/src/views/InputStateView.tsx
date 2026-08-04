import type { RuntimeObservabilityViewModel } from "../viewModels/runtimeObservability";

export default function InputStateView({
  vm,
}: {
  vm: RuntimeObservabilityViewModel;
}) {
  if (vm.inputState.status === "unavailable" || vm.inputState.status === "empty") {
    return <div className="ide-runtime-empty">No input state reported.</div>;
  }

  return (
    <div className="ide-runtime-section" data-input-state="phase-4-5-c2-b">
      <div className="ide-section-title">Input State</div>
      {vm.inputState.states.map((state) => (
        <div className="ide-runtime-card" key={state.id}>
          <div className="ide-runtime-card-title">
            <span>{state.name ?? state.id}</span>
            <strong>{state.stateType ?? "InputState"}</strong>
          </div>
          <div className="ide-runtime-muted">id: {state.id}</div>
          {state.source && <div className="ide-runtime-muted">source: {state.source}</div>}
          {state.consumedBy && state.consumedBy.length > 0 && (
            <div className="ide-runtime-muted">consumed by: {state.consumedBy.join(", ")}</div>
          )}
          {state.value != null && <pre className="ide-runtime-value">{String(state.value)}</pre>}
        </div>
      ))}
    </div>
  );
}
