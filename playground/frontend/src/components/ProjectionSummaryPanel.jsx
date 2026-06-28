import './ProjectionSummaryPanel.css'

function entriesFromSummary(data) {
  if (!data) return []
  if (Array.isArray(data.modules)) return data.modules
  return [data]
}

function SummaryEntry({ entry }) {
  const core = entry.normalized_core ?? {}
  return (
    <div className="projection-summary-entry">
      <div className="projection-summary-grid">
        <div>
          <span>Source Kind</span>
          <strong>{entry.source_kind ?? 'unknown'}</strong>
        </div>
        <div>
          <span>Syntax Status</span>
          <strong>{entry.syntax_status ?? 'unknown'}</strong>
        </div>
        <div>
          <span>Construct Type</span>
          <strong>{entry.construct_type ?? 'unknown'}</strong>
        </div>
        <div>
          <span>Normalized Core</span>
          <strong>{core.kind ?? 'ReasonGraph'}(namespace="{core.namespace ?? 'unknown'}")</strong>
        </div>
        <div className="wide">
          <span>Core Semantics</span>
          <strong>{entry.core_semantics ?? 'identical for v0.6-C'}</strong>
        </div>
      </div>
      {entry.normalization_display && (
        <div className="projection-summary-note">{entry.normalization_display}</div>
      )}
    </div>
  )
}

export default function ProjectionSummaryPanel({ data }) {
  const entries = entriesFromSummary(data)
  if (entries.length === 0) {
    return <div className="panel-empty">Summary がありません</div>
  }
  return (
    <div className="projection-summary-panel">
      {entries.map((entry, index) => (
        <SummaryEntry key={`${entry.source_kind}-${entry.normalized_core?.namespace ?? index}`} entry={entry} />
      ))}
    </div>
  )
}
