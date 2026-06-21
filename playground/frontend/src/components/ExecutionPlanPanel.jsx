import JsonViewer from './JsonViewer.jsx'
import './PipelinePanel.css'

function StepFlow({ steps }) {
  if (!steps || steps.length === 0) return <p className="pp-empty-msg">Steps なし</p>
  return (
    <div className="pp-flow">
      {steps.map((step, i) => (
        <div key={i} className="pp-flow-item">
          {i === 0 && (
            <div className="pp-flow-node pp-node-start">{step.source}</div>
          )}
          <div className="pp-flow-arrow">
            <span className="pp-flow-label">{step.transition_id}</span>
            <span className="pp-arrow">↓</span>
          </div>
          <div className={`pp-flow-node ${i === steps.length - 1 ? 'pp-node-goal' : ''}`}>
            {step.target}
          </div>
        </div>
      ))}
    </div>
  )
}

export default function ExecutionPlanPanel({ data }) {
  if (!data) return (
    <div className="pp-empty">
      <div className="pp-empty-icon">📋</div>
      <div className="pp-empty-msg">Run を実行すると ExecutionPlan が表示されます</div>
    </div>
  )

  const steps = data.selected_steps ?? []
  const alts = data.alternative_paths ?? []

  return (
    <div className="pp-root">
      {/* Summary */}
      <div className="pp-section">
        <div className="pp-section-title">Summary</div>
        <div className="pp-summary-grid">
          <div className="pp-kv"><span className="pp-key">Goal</span><span className="pp-val pp-tag">{data.goal ?? '—'}</span></div>
          <div className="pp-kv"><span className="pp-key">Distance</span><span className="pp-val">{data.distance ?? 0}</span></div>
          <div className="pp-kv"><span className="pp-key">Cost</span><span className="pp-val">{data.expected_cost?.toFixed(2) ?? '—'}</span></div>
          <div className="pp-kv">
            <span className="pp-key">Reachable</span>
            <span className={`pp-badge ${data.reachable ? 'pp-badge-ok' : 'pp-badge-err'}`}>
              {data.reachable ? 'true' : 'false'}
            </span>
          </div>
          <div className="pp-kv"><span className="pp-key">Step Count</span><span className="pp-val">{steps.length}</span></div>
          <div className="pp-kv"><span className="pp-key">Alt Paths</span><span className="pp-val">{alts.length}</span></div>
        </div>
      </div>

      {/* Plan Steps flow */}
      <div className="pp-section">
        <div className="pp-section-title">Plan Steps</div>
        <StepFlow steps={steps} />
      </div>

      {/* Alternative paths */}
      {alts.length > 0 && (
        <div className="pp-section">
          <div className="pp-section-title">Alternative Paths</div>
          {alts.map((alt, i) => (
            <div key={i} className="pp-alt-row">
              <span className="pp-alt-label">Path {i + 1}</span>
              <span className="pp-alt-cost">cost {alt.expected_cost?.toFixed(2)}</span>
              <span className="pp-alt-steps">{alt.step_ids?.length ?? 0} steps</span>
            </div>
          ))}
        </div>
      )}

      {/* Raw JSON */}
      <div className="pp-section pp-section-raw">
        <div className="pp-section-title">Raw JSON</div>
        <JsonViewer data={data} />
      </div>
    </div>
  )
}
