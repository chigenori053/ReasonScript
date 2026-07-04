import type { LanguageAuditViewModel } from "../viewModels/languageAudit";
import JsonArtifactView from "./JsonArtifactView";

export default function LanguageAuditArtifactsView({
  vm,
}: {
  vm: LanguageAuditViewModel;
}) {
  return (
    <div className="ide-artifact-workflow" data-language-audit-artifacts="phase-4-5-c2-d">
      <div className="ide-artifact-workflow-section">
        <div className="ide-section-title">Raw Audit Report</div>
        {vm.raw == null ? (
          <div className="ide-tool-empty">Language audit unavailable.</div>
        ) : (
          <JsonArtifactView data={vm.raw} label="Raw Audit Report" />
        )}
      </div>
      <div className="ide-artifact-workflow-section">
        <div className="ide-section-title">Raw Language Audit Matrix JSON</div>
        {vm.matrix.length === 0 ? (
          <div className="ide-tool-empty">No language audit matrix available.</div>
        ) : (
          <JsonArtifactView data={vm.matrix} label="Raw Language Audit Matrix JSON" />
        )}
      </div>
      <div className="ide-artifact-workflow-section">
        <div className="ide-section-title">Audit Export Result</div>
        {!vm.exportResult ? (
          <div className="ide-tool-empty">Audit export unavailable.</div>
        ) : (
          <>
            <div className="ide-artifact-row"><span>Status</span><strong>{vm.exportResult.status}</strong></div>
            {vm.exportResult.exportPath && (
              <div className="ide-artifact-row"><span>Export path</span><strong>{vm.exportResult.exportPath}</strong></div>
            )}
            {vm.exportResult.matrixVersion && (
              <div className="ide-artifact-row"><span>Matrix version</span><strong>{vm.exportResult.matrixVersion}</strong></div>
            )}
            <JsonArtifactView data={vm.exportResult.raw} label="Audit Export Result" />
          </>
        )}
      </div>
    </div>
  );
}
