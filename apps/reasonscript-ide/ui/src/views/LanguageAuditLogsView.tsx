import type { LanguageAuditViewModel } from "../viewModels/languageAudit";

export default function LanguageAuditLogsView({
  vm,
}: {
  vm: LanguageAuditViewModel;
}) {
  if (vm.logs.length === 0) {
    return <div className="ide-runtime-empty">No audit operation logs.</div>;
  }

  return (
    <div className="ide-runtime-section" data-audit-operation-logs="phase-4-5-c2-d">
      <div className="ide-section-title">Audit Operation Logs</div>
      {vm.logs.map((log) => (
        <div className="ide-runtime-row" key={log.id}>
          <span className="ide-runtime-kind">audit</span>
          {log.status && <span className="ide-runtime-muted">{log.status}</span>}
          {log.timestamp && <span className="ide-runtime-muted">{log.timestamp}</span>}
          <span className="ide-runtime-message">{log.message}</span>
        </div>
      ))}
    </div>
  );
}
