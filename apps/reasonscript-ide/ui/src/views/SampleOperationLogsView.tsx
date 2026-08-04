import type { SampleBrowserViewModel } from "../viewModels/sampleBrowser";

export default function SampleOperationLogsView({ vm }: { vm: SampleBrowserViewModel }) {
  if (vm.logs.length === 0) {
    return <div className="ide-runtime-empty">No sample operation logs.</div>;
  }

  return (
    <div className="ide-runtime-section" data-sample-operation-logs="phase-4-5-c2-e">
      <div className="ide-section-title">Sample Load Logs</div>
      {vm.logs.map((log) => (
        <div className="ide-runtime-row" key={log.id}>
          <span className="ide-runtime-kind">sample</span>
          {log.status && <span className="ide-runtime-muted">{log.status}</span>}
          {log.timestamp && <span className="ide-runtime-muted">{log.timestamp}</span>}
          <span className="ide-runtime-message">{log.message}</span>
        </div>
      ))}
    </div>
  );
}
