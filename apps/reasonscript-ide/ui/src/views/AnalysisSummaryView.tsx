import {
  analysisStatusLabel,
  complexitySummaryLabel,
  typeCoverageLabel,
  type DiagnosticsAnalysisViewModel,
} from "../viewModels/analysisDiagnostics";

function SummaryMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="ide-summary-metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export default function AnalysisSummaryView({
  vm,
}: {
  vm: DiagnosticsAnalysisViewModel;
}) {
  const cycleLabel = vm.cycle.status === "unavailable"
    ? "unavailable"
    : vm.cycle.status === "pass"
      ? "none"
      : `${vm.cycle.cycleCount ?? vm.cycle.diagnostics.length} found`;
  const ownershipLabel = vm.ownership.status === "unavailable"
    ? "unavailable"
    : `${vm.ownership.producerCount ?? 0} producers / ${vm.ownership.consumerCount ?? 0} consumers`;
  const determinismLabel = vm.determinism.status === "unavailable"
    ? "unavailable"
    : vm.determinism.deterministic
      ? "deterministic"
      : "non-deterministic";

  return (
    <section className="ide-result-card" data-analysis-summary="phase-4-5-c2-a">
      <div className="ide-section-title">Overview Analysis Summary</div>
      <div className="ide-summary-grid">
        <SummaryMetric label="Strict" value={analysisStatusLabel(vm.strict.status)} />
        <SummaryMetric label="Cycle" value={cycleLabel} />
        <SummaryMetric label="Exhaustiveness" value={analysisStatusLabel(vm.exhaustiveness.status)} />
        <SummaryMetric label="Type Coverage" value={typeCoverageLabel(vm)} />
        <SummaryMetric label="Ownership" value={ownershipLabel} />
        <SummaryMetric label="Determinism" value={determinismLabel} />
        <SummaryMetric label="Complexity" value={complexitySummaryLabel(vm)} />
      </div>
    </section>
  );
}
