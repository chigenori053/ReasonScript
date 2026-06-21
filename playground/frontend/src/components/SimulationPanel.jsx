import JsonViewer from './JsonViewer.jsx'
import './PipelinePanel.css'

function TraceFlow({ trace }) {
  if (!trace || trace.length === 0) return <p className="pp-empty-msg">Trace なし</p>
  return (
    <div className="pp-flow">
      {trace.map((step, i) => (
        <div key={i} className="pp-flow-item">
          <div className={`pp-flow-node ${i === 0 ? 'pp-node-start' : i === trace.length - 1 ? 'pp-node-goal' : ''}`}>
            {step.state}
          </div>
          {i < trace.length - 1 && (
            <div className="pp-flow-arrow">
              <span className="pp-flow-label">{trace[i + 1]?.transition ?? ''}</span>
              <span className="pp-arrow">↓</span>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

function StateTable({ trace }) {
  if (!trace || trace.length === 0) return null
  return (
    <table className="pp-table">
      <thead>
        <tr><th>Step</th><th>State</th><th>Event</th></tr>
      </thead>
      <tbody>
        {trace.map((row, i) => (
          <tr key={i} className={i === trace.length - 1 ? 'pp-row-final' : ''}>
            <td>{row.step}</td>
            <td><span className="pp-tag">{row.state}</span></td>
            <td className="pp-cell-dim">{row.transition ?? row.event ?? '—'}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export default function SimulationPanel({ data }) {
  if (!data) return (
    <div className="pp-empty">
      <div className="pp-empty-icon">🔄</div>
      <div className="pp-empty-msg">Run を実行すると Simulation 結果が表示されます</div>
    </div>
  )

  const trace = data.trace ?? []
  const violations = data.violations ?? []

  return (
    <div className="pp-root">
      {/* Summary */}
      <div className="pp-section">
        <div className="pp-section-title">Summary</div>
        <div className="pp-summary-grid">
          <div className="pp-kv">
            <span className="pp-key">Success</span>
            <span className={`pp-badge ${data.success ? 'pp-badge-ok' : 'pp-badge-err'}`}>
              {String(data.success)}
            </span>
          </div>
          <div className="pp-kv">
            <span className="pp-key">Goal Reached</span>
            <span className={`pp-badge ${data.goal_reached ? 'pp-badge-ok' : 'pp-badge-warn'}`}>
              {String(data.goal_reached)}
            </span>
          </div>
          <div className="pp-kv"><span className="pp-key">Cost</span><span className="pp-val">{data.cost?.toFixed(2) ?? '—'}</span></div>
          <div className="pp-kv"><span className="pp-key">Confidence</span>
            <span className="pp-val pp-confidence">
              <span className="pp-conf-bar" style={{ width: `${(data.confidence ?? 0) * 100}%` }} />
              {((data.confidence ?? 0) * 100).toFixed(0)}%
            </span>
          </div>
          <div className="pp-kv"><span className="pp-key">Steps</span><span className="pp-val">{data.step_count ?? 0}</span></div>
          <div className="pp-kv"><span className="pp-key">Final State</span><span className="pp-val pp-tag">{data.final_state ?? '—'}</span></div>
        </div>
        {violations.length > 0 && (
          <div className="pp-violations">
            <span className="pp-violations-label">Violations:</span>
            {violations.map((v, i) => <span key={i} className="pp-badge pp-badge-err">{v}</span>)}
          </div>
        )}
      </div>

      {/* Trace flow */}
      <div className="pp-section">
        <div className="pp-section-title">Trace</div>
        <TraceFlow trace={trace} />
      </div>

      {/* State Table */}
      <div className="pp-section">
        <div className="pp-section-title">State Table</div>
        <StateTable trace={trace} />
      </div>

      {/* Raw JSON */}
      <div className="pp-section pp-section-raw">
        <div className="pp-section-title">Raw JSON</div>
        <JsonViewer data={data} />
      </div>
    </div>
  )
}
