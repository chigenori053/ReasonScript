import {
  runtimeStatusLabel,
  type RuntimeObservabilityViewModel,
} from "../viewModels/runtimeObservability";

function SummaryMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="ide-summary-metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export default function RuntimeObservabilitySummaryView({
  vm,
}: {
  vm: RuntimeObservabilityViewModel;
}) {
  return (
    <section className="ide-result-card" data-runtime-summary="phase-4-5-c2-b">
      <div className="ide-section-title">Overview Runtime Summary</div>
      <div className="ide-summary-grid">
        <SummaryMetric label="Runtime IO" value={runtimeStatusLabel(vm.runtimeOutput.status)} />
        <SummaryMetric label="Input State" value={runtimeStatusLabel(vm.inputState.status)} />
        <SummaryMetric label="Calculation" value={runtimeStatusLabel(vm.calculation.status)} />
        <SummaryMetric label="Runtime Trace" value={runtimeStatusLabel(vm.runtimeTrace.status)} />
      </div>
    </section>
  );
}
