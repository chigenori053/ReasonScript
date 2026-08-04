import { useState } from "react";
import JsonArtifactView from "./JsonArtifactView";
import type { ImportArtifactResult } from "../viewModels/artifactWorkflow";

export default function ImportArtifactView({
  result,
  onImport,
  disabled,
}: {
  result: ImportArtifactResult;
  onImport: (path: string) => void;
  disabled?: boolean;
}) {
  const [path, setPath] = useState("");
  return (
    <div className="ide-artifact-workflow-section" data-import-migration-surface="phase-4-5-c2-c">
      <div className="ide-artifact-workflow-head">
        <div>
          <div className="ide-section-title">Artifact Import</div>
          <div className="ide-muted-note">Validation-first import; failed import does not mutate editor content.</div>
        </div>
      </div>
      <div className="ide-inline-form">
        <input
          value={path}
          onChange={(event) => setPath(event.target.value)}
          placeholder="playground/exports/sample_001"
        />
        <button className="toolbar-btn" onClick={() => onImport(path)} disabled={disabled || !path.trim()}>
          Import
        </button>
      </div>
      {result.status === "idle" && <div className="ide-tool-empty">No import has been run.</div>}
      {result.status === "unavailable" && <div className="ide-tool-empty">Import unavailable.</div>}
      {result.status !== "idle" && result.status !== "unavailable" && (
        <div className="ide-artifact-workflow-body">
          <div className="ide-artifact-row"><span>Status</span><strong>{result.status}</strong></div>
          {result.importedFiles && <div className="ide-artifact-row"><span>Imported files</span><strong>{result.importedFiles.length}</strong></div>}
          {result.restoredArtifacts && <div className="ide-artifact-row"><span>Restored artifacts</span><strong>{result.restoredArtifacts.length}</strong></div>}
          <div className="ide-artifact-row"><span>Validation issues</span><strong>{result.validationIssues.length}</strong></div>
          <details className="ide-artifact-details">
            <summary>Raw import result</summary>
            <JsonArtifactView data={result.raw} label="Raw Import Result" />
          </details>
        </div>
      )}
    </div>
  );
}
