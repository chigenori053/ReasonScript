import type { ArtifactWorkflowViewModel } from "../viewModels/artifactWorkflow";

function statusText(status: string | undefined) {
  return status ?? "idle";
}

export default function ArtifactWorkflowSummaryView({
  vm,
}: {
  vm: ArtifactWorkflowViewModel;
}) {
  return (
    <section className="ide-overview-section ide-artifact-workflow-summary" data-artifact-workflow-summary="phase-4-5-c2-c">
      <div className="ide-section-title">Artifact Workflow Summary</div>
      <div className="ide-summary-grid">
        <div className="ide-summary-metric">
          <span>Export</span>
          <strong>{statusText(vm.exportResult.status)}</strong>
        </div>
        <div className="ide-summary-metric">
          <span>Import</span>
          <strong>{statusText(vm.importResult.status)}</strong>
        </div>
        <div className="ide-summary-metric">
          <span>Diff</span>
          <strong>{statusText(vm.diffResult.status)}</strong>
        </div>
        <div className="ide-summary-metric">
          <span>Last operation</span>
          <strong>{vm.summary.lastOperation ?? "none"}</strong>
        </div>
        <div className="ide-summary-metric">
          <span>Issues</span>
          <strong>{vm.summary.issueCount}</strong>
        </div>
        <div className="ide-summary-metric">
          <span>Logs</span>
          <strong>{vm.summary.logCount}</strong>
        </div>
      </div>
    </section>
  );
}
