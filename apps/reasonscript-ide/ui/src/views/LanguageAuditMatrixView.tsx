import type { LanguageAuditViewModel } from "../viewModels/languageAudit";

export default function LanguageAuditMatrixView({
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
    <div className="ide-language-audit-matrix" data-language-audit-matrix="phase-4-5-c2-d">
      <div className="ide-artifact-workflow-head">
        <div>
          <div className="ide-section-title">Language Audit Matrix</div>
          <div className="ide-muted-note">Feature category rows verify expected and actual integration status.</div>
        </div>
        <div className="ide-button-row">
          <button className="toolbar-btn" onClick={onRunAudit} disabled={disabled}>Run Audit</button>
          <button className="toolbar-btn secondary" onClick={onExportAudit} disabled={disabled}>Export</button>
        </div>
      </div>

      <div className="ide-summary-grid">
        <div className="ide-summary-metric"><span>Connected</span><strong>{vm.summary.connectedCount}</strong></div>
        <div className="ide-summary-metric"><span>Missing</span><strong>{vm.summary.missingCount}</strong></div>
        <div className="ide-summary-metric"><span>Warning</span><strong>{vm.summary.warningCount}</strong></div>
        <div className="ide-summary-metric"><span>Error</span><strong>{vm.summary.errorCount}</strong></div>
      </div>

      {vm.matrix.length === 0 ? (
        <div className="ide-tool-empty">
          No language audit matrix available.
        </div>
      ) : (
        <div className="ide-audit-table">
          <div className="ide-audit-row header">
            <span>Category</span>
            <span>Feature</span>
            <span>Expected</span>
            <span>Actual</span>
            <strong>Status</strong>
          </div>
          {vm.matrix.map((row) => (
            <div className={`ide-audit-row ${row.status}`} key={row.id}>
              <span>{row.category}</span>
              <span>{row.feature}</span>
              <span>{row.expected}</span>
              <span>{row.actual ?? "unknown"}</span>
              <strong>{row.status}</strong>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
