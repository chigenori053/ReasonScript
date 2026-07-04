import type { WorkspaceDiagnosticsViewModel } from "../viewModels/workspaceDiagnostics";

function SummaryMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="ide-summary-metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export default function WorkspaceDiagnosticsSummaryView({
  vm,
}: {
  vm: WorkspaceDiagnosticsViewModel;
}) {
  return (
    <section className="ide-result-card" data-workspace-diagnostics-summary="phase-5-1">
      <div className="ide-section-title">Workspace Diagnostics Summary</div>
      {!vm.available ? (
        <div className="ide-muted-note">No workspace opened.</div>
      ) : (
        <>
          <div className="ide-summary-grid">
            <SummaryMetric label="Scan status" value={vm.scanStatus} />
            <SummaryMetric label="Valid files" value={String(vm.validFileCount)} />
            <SummaryMetric label="Invalid files" value={String(vm.invalidFileCount)} />
            <SummaryMetric label="Unsupported files" value={String(vm.unsupportedFileCount)} />
            <SummaryMetric label="Ignored paths" value={String(vm.ignoredPaths.length)} />
          </div>
          {vm.scanTruncated && (
            <div className="ide-warning-note">Scan limit reached; workspace listing may be incomplete.</div>
          )}
        </>
      )}
    </section>
  );
}
