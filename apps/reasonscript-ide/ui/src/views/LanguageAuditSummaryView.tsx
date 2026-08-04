import type { LanguageAuditViewModel } from "../viewModels/languageAudit";

export default function LanguageAuditSummaryView({
  vm,
  onRunAudit,
  onExportAudit,
  disabled,
}: {
  vm: LanguageAuditViewModel;
  onRunAudit: () => void;
  onExportAudit: () => void;
  disabled?: boolean;
}) {
  return (
    <section className="ide-overview-section ide-language-audit-summary" data-language-audit-summary="phase-4-5-c2-d">
      <div className="ide-artifact-workflow-head">
        <div>
          <div className="ide-section-title">Audit Summary</div>
          <div className="ide-muted-note">Language surface, compiler, runtime, and IDE integration audit.</div>
        </div>
        <div className="ide-button-row">
          <button className="toolbar-btn" onClick={onRunAudit} disabled={disabled}>Run Audit</button>
          <button className="toolbar-btn secondary" onClick={onExportAudit} disabled={disabled}>Export</button>
        </div>
      </div>
      <div className="ide-summary-grid">
        <div className="ide-summary-metric"><span>Audit</span><strong>{vm.summary.status}</strong></div>
        <div className="ide-summary-metric"><span>Connected items</span><strong>{vm.summary.connectedCount}</strong></div>
        <div className="ide-summary-metric"><span>Missing items</span><strong>{vm.summary.missingCount}</strong></div>
        <div className="ide-summary-metric"><span>Warning items</span><strong>{vm.summary.warningCount}</strong></div>
        <div className="ide-summary-metric"><span>Error items</span><strong>{vm.summary.errorCount}</strong></div>
        <div className="ide-summary-metric"><span>Last audit run</span><strong>{vm.summary.lastRunAt ?? "unavailable"}</strong></div>
      </div>
      {vm.summary.status === "unavailable" && (
        <div className="ide-tool-empty">No language audit has been run.</div>
      )}
    </section>
  );
}
