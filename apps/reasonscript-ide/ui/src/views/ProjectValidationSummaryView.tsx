import { projectValidationStatusLabel, type ProjectValidationSummary } from "../viewModels/projectValidation";

function SummaryMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="ide-summary-metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export default function ProjectValidationSummaryView({
  summary,
}: {
  summary: ProjectValidationSummary;
}) {
  return (
    <section className="ide-result-card" data-project-validation-summary="phase-5-5">
      <div className="ide-section-title">Project Validation Summary</div>
      <div className="ide-summary-grid">
        <SummaryMetric label="Status" value={projectValidationStatusLabel(summary.status)} />
        <SummaryMetric label="Valid files" value={String(summary.validFileCount)} />
        <SummaryMetric label="Invalid files" value={String(summary.invalidFileCount)} />
        <SummaryMetric label="Ignored files" value={String(summary.ignoredFileCount)} />
        <SummaryMetric label="Diagnostics" value={`${summary.errorCount} errors / ${summary.warningCount} warnings`} />
        <SummaryMetric label="Can analyze" value={summary.canAnalyze ? "yes" : "no"} />
        <SummaryMetric label="Can run" value={summary.canRun ? "yes" : "no"} />
      </div>
      {summary.reason && <div className="ide-muted-note">{summary.reason}</div>}
    </section>
  );
}
