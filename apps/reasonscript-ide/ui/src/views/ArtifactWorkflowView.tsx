import type { ArtifactWorkflowViewModel } from "../viewModels/artifactWorkflow";
import DiffArtifactView from "./DiffArtifactView";
import ExportArtifactView from "./ExportArtifactView";
import ImportArtifactView from "./ImportArtifactView";

export default function ArtifactWorkflowView({
  vm,
  slotAReady,
  slotBReady,
  onExport,
  onImport,
  onSetDiffSlot,
  onCompareDiff,
  disabled,
}: {
  vm: ArtifactWorkflowViewModel;
  slotAReady: boolean;
  slotBReady: boolean;
  onExport: () => void;
  onImport: (path: string) => void;
  onSetDiffSlot: (slot: "a" | "b") => void;
  onCompareDiff: () => void;
  disabled?: boolean;
}) {
  return (
    <div className="ide-artifact-workflow" data-artifacts-export-import-diff="phase-4-5-c2-c">
      <ExportArtifactView result={vm.exportResult} onExport={onExport} disabled={disabled} />
      <ImportArtifactView result={vm.importResult} onImport={onImport} disabled={disabled} />
      <DiffArtifactView
        result={vm.diffResult}
        slotAReady={slotAReady}
        slotBReady={slotBReady}
        onSetSlot={onSetDiffSlot}
        onCompare={onCompareDiff}
        disabled={disabled}
      />
      <div className="ide-artifact-workflow-section">
        <div className="ide-section-title">Artifact Workflow Issues</div>
        {vm.issues.length === 0 ? (
          <div className="ide-tool-empty">No artifact workflow issues.</div>
        ) : (
          vm.issues.map((issue) => (
            <div className="ide-analysis-diagnostic-row" key={issue.id}>
              <span className={`ide-analysis-severity ${issue.severity}`}>{issue.severity}</span>
              <span className="ide-analysis-feature">{issue.operation}</span>
              {issue.code && <span className="ide-analysis-code">{issue.code}</span>}
              <span className="ide-analysis-message">{issue.message}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
