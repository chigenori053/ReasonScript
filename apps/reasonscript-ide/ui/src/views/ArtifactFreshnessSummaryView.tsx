import type { ArtifactFreshnessViewModel } from "../viewModels/artifactFreshness";

export default function ArtifactFreshnessSummaryView({
  vm,
}: {
  vm: ArtifactFreshnessViewModel;
}) {
  return (
    <section className="ide-result-card" data-artifact-freshness-summary="phase-5-4">
      <div className="ide-section-title">Artifact Freshness Summary</div>
      <div className="ide-summary-grid">
        {vm.items.map((item) => (
          <div className="ide-summary-metric" key={item.artifactName}>
            <span>{item.artifactName}</span>
            <strong>{item.status}</strong>
          </div>
        ))}
      </div>
      {vm.overallStatus === "stale" && (
        <div className="ide-warning-note">
          Source has changed since the last Analyze run; artifacts shown may be stale.
        </div>
      )}
    </section>
  );
}
