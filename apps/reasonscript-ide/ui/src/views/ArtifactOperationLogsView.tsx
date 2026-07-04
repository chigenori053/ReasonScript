import type { ArtifactWorkflowViewModel } from "../viewModels/artifactWorkflow";

export default function ArtifactOperationLogsView({
  vm,
}: {
  vm: ArtifactWorkflowViewModel;
}) {
  if (vm.logs.length === 0) {
    return <div className="ide-runtime-empty">No artifact workflow logs.</div>;
  }

  return (
    <div className="ide-runtime-section" data-artifact-operation-logs="phase-4-5-c2-c">
      <div className="ide-section-title">Artifact Operation Logs</div>
      {vm.logs.map((log) => (
        <div className="ide-runtime-row" key={log.id}>
          <span className="ide-runtime-kind">{log.operation}</span>
          {log.status && <span className="ide-runtime-muted">{log.status}</span>}
          {log.timestamp && <span className="ide-runtime-muted">{log.timestamp}</span>}
          <span className="ide-runtime-message">{log.message}</span>
        </div>
      ))}
    </div>
  );
}
