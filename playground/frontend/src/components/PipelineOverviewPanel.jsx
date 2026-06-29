import JsonViewer from './JsonViewer.jsx'
import './PipelinePanel.css'

const STATUS_CLASS = {
  success: 'pp-badge-ok',
  warning: 'pp-badge-warn',
  error: 'pp-badge-err',
  skipped: 'pp-badge-warn',
  unavailable: '',
}

export default function PipelineOverviewPanel({ data }) {
  if (!data) {
    return (
      <div className="pp-empty">
        <div className="pp-empty-icon">PIPE</div>
        <div className="pp-empty-msg">Run or Analyze to inspect pipeline status.</div>
      </div>
    )
  }

  const stages = Array.isArray(data.stages) ? data.stages : []

  return (
    <div className="pp-root">
      <div className="pp-section">
        <div className="pp-section-title">Pipeline Overview</div>
        <table className="pp-table">
          <thead>
            <tr>
              <th>Stage</th>
              <th>Status</th>
              <th>Artifact</th>
              <th>Diagnostics</th>
            </tr>
          </thead>
          <tbody>
            {stages.map(stage => (
              <tr key={stage.id}>
                <td><span className="pp-tag pp-tag-sm">{stage.name}</span></td>
                <td>
                  <span className={`pp-badge pp-badge-sm ${STATUS_CLASS[stage.status] ?? ''}`}>
                    {stage.status}
                  </span>
                </td>
                <td className="pp-cell-dim">{stage.artifact ?? 'source text'}</td>
                <td>{stage.diagnostic_count ?? 0}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="pp-section pp-section-raw">
        <div className="pp-section-title">Raw JSON</div>
        <JsonViewer data={data} />
      </div>
    </div>
  )
}
