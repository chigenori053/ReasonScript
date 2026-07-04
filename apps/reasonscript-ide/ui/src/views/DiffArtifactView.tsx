import JsonArtifactView from "./JsonArtifactView";
import type { DiffArtifactResult } from "../viewModels/artifactWorkflow";

export default function DiffArtifactView({
  result,
  slotAReady,
  slotBReady,
  onSetSlot,
  onCompare,
  disabled,
}: {
  result: DiffArtifactResult;
  slotAReady: boolean;
  slotBReady: boolean;
  onSetSlot: (slot: "a" | "b") => void;
  onCompare: () => void;
  disabled?: boolean;
}) {
  return (
    <div className="ide-artifact-workflow-section" data-diff-migration-surface="phase-4-5-c2-c">
      <div className="ide-artifact-workflow-head">
        <div>
          <div className="ide-section-title">Artifact Diff</div>
          <div className="ide-muted-note">Compare current artifact with imported or baseline artifact slots.</div>
        </div>
        <div className="ide-button-row">
          <button className="toolbar-btn secondary" onClick={() => onSetSlot("a")} disabled={disabled}>Set A</button>
          <button className="toolbar-btn secondary" onClick={() => onSetSlot("b")} disabled={disabled}>Set B</button>
          <button className="toolbar-btn" onClick={onCompare} disabled={disabled || !slotAReady || !slotBReady}>Compare</button>
        </div>
      </div>
      <div className="ide-slot-grid">
        <div className={slotAReady ? "ide-slot ready" : "ide-slot"}>A {slotAReady ? "READY" : "EMPTY"}</div>
        <div className={slotBReady ? "ide-slot ready" : "ide-slot"}>B {slotBReady ? "READY" : "EMPTY"}</div>
      </div>
      {result.status === "idle" && <div className="ide-tool-empty">No diff has been run.</div>}
      {result.status === "unavailable" && <div className="ide-tool-empty">Diff unavailable.</div>}
      {result.status !== "idle" && result.status !== "unavailable" && (
        <div className="ide-artifact-workflow-body">
          <div className="ide-summary-grid">
            <div className="ide-summary-metric"><span>Status</span><strong>{result.status}</strong></div>
            <div className="ide-summary-metric"><span>Changed</span><strong>{result.summary?.changed ?? 0}</strong></div>
            <div className="ide-summary-metric"><span>Added</span><strong>{result.summary?.added ?? 0}</strong></div>
            <div className="ide-summary-metric"><span>Removed</span><strong>{result.summary?.removed ?? 0}</strong></div>
            <div className="ide-summary-metric"><span>Unchanged</span><strong>{result.summary?.unchanged ?? 0}</strong></div>
            <div className="ide-summary-metric"><span>Issues</span><strong>{result.issues.length}</strong></div>
          </div>
          <details className="ide-artifact-details">
            <summary>Raw diff result</summary>
            <JsonArtifactView data={result.raw} label="Raw Diff Result" />
          </details>
        </div>
      )}
    </div>
  );
}
