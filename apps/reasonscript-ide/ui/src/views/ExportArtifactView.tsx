import JsonArtifactView from "./JsonArtifactView";
import type { ExportArtifactResult } from "../viewModels/artifactWorkflow";

export default function ExportArtifactView({
  result,
  onExport,
  disabled,
}: {
  result: ExportArtifactResult;
  onExport: () => void;
  disabled?: boolean;
}) {
  return (
    <div className="ide-artifact-workflow-section" data-export-migration-surface="phase-4-5-c2-c">
      <div className="ide-artifact-workflow-head">
        <div>
          <div className="ide-section-title">Artifact Export</div>
          <div className="ide-muted-note">Export current analyze result, current file, and artifact bundle.</div>
        </div>
        <button className="toolbar-btn" onClick={onExport} disabled={disabled}>
          Export
        </button>
      </div>
      {result.status === "idle" && <div className="ide-tool-empty">No export has been run.</div>}
      {result.status === "unavailable" && <div className="ide-tool-empty">Export unavailable.</div>}
      {result.status !== "idle" && result.status !== "unavailable" && (
        <div className="ide-artifact-workflow-body">
          <div className="ide-artifact-row"><span>Status</span><strong>{result.status}</strong></div>
          {result.artifactId && <div className="ide-artifact-row"><span>Artifact ID</span><strong>{result.artifactId}</strong></div>}
          {result.artifactName && <div className="ide-artifact-row"><span>Name</span><strong>{result.artifactName}</strong></div>}
          {result.artifactPath && <div className="ide-artifact-row"><span>Path</span><strong>{result.artifactPath}</strong></div>}
          {result.files && <div className="ide-artifact-row"><span>Files</span><strong>{result.files.length}</strong></div>}
          <details className="ide-artifact-details">
            <summary>Raw export result</summary>
            <JsonArtifactView data={result.raw} label="Raw Export Result" />
          </details>
        </div>
      )}
    </div>
  );
}
