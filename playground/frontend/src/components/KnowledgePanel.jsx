import { useState } from 'react'
import JsonViewer from './JsonViewer.jsx'
import './PipelinePanel.css'

function ConfidenceBar({ value }) {
  const pct = Math.round((value ?? 0) * 100)
  const cls = pct >= 80 ? 'high' : pct >= 50 ? 'mid' : 'low'
  return (
    <span className={`pp-confidence pp-conf-${cls}`}>
      <span className="pp-conf-bar" style={{ width: `${pct}%` }} />
      {pct}%
    </span>
  )
}

function EvidencePath({ path }) {
  if (!path || path.length === 0) return null
  return (
    <div className="pp-evidence-path">
      {path.map((node, i) => (
        <span key={i}>
          <span className="pp-tag pp-tag-sm">{node}</span>
          {i < path.length - 1 && <span className="pp-arrow-inline"> ↓ </span>}
        </span>
      ))}
    </div>
  )
}

export default function KnowledgePanel({ data }) {
  const [expanded, setExpanded] = useState(null)

  if (!data) return (
    <div className="pp-empty">
      <div className="pp-empty-icon">💡</div>
      <div className="pp-empty-msg">Run を実行すると Knowledge が表示されます</div>
    </div>
  )

  const units = data.knowledge ?? []

  return (
    <div className="pp-root">
      {/* Summary */}
      <div className="pp-section">
        <div className="pp-section-title">Summary</div>
        <div className="pp-summary-grid">
          <div className="pp-kv"><span className="pp-key">Knowledge Count</span><span className="pp-val">{data.knowledge_count ?? 0}</span></div>
          <div className="pp-kv"><span className="pp-key">Evidence Count</span><span className="pp-val">{data.evidence_count ?? 0}</span></div>
          <div className="pp-kv"><span className="pp-key">Generated At</span><span className="pp-val pp-dim">{data.generated_at ? new Date(data.generated_at).toLocaleTimeString() : '—'}</span></div>
        </div>
      </div>

      {/* Knowledge list */}
      <div className="pp-section">
        <div className="pp-section-title">Knowledge List</div>
        {units.length === 0 ? (
          <p className="pp-empty-msg">Knowledge ユニットなし</p>
        ) : (
          <div className="pp-knowledge-list">
            {units.map((unit, i) => (
              <div
                key={i}
                className={`pp-knowledge-card ${expanded === i ? 'expanded' : ''}`}
                onClick={() => setExpanded(expanded === i ? null : i)}
              >
                <div className="pp-kcard-header">
                  <span className="pp-kcard-id">{unit.id}</span>
                  <span className="pp-kcard-relation">
                    <span className="pp-tag">{unit.source}</span>
                    <span className="pp-rel-arrow"> —[{unit.relation}]→ </span>
                    <span className="pp-tag">{unit.target}</span>
                  </span>
                  <ConfidenceBar value={unit.confidence} />
                  {unit.from_simulation && <span className="pp-badge pp-badge-ok pp-badge-sm">sim</span>}
                  <span className="pp-chevron">{expanded === i ? '▲' : '▼'}</span>
                </div>
                {expanded === i && (
                  <div className="pp-kcard-body">
                    <div className="pp-kv">
                      <span className="pp-key">Path Length</span>
                      <span className="pp-val">{unit.path_length}</span>
                    </div>
                    {unit.evidence?.path && (
                      <div className="pp-kv pp-kv-col">
                        <span className="pp-key">Evidence Path</span>
                        <EvidencePath path={unit.evidence.path} />
                      </div>
                    )}
                    {unit.evidence?.transitions && (
                      <div className="pp-kv pp-kv-col">
                        <span className="pp-key">Transitions</span>
                        <div className="pp-tag-row">
                          {unit.evidence.transitions.map((t, j) => (
                            <span key={j} className="pp-tag pp-tag-sm">{t}</span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Raw JSON */}
      <div className="pp-section pp-section-raw">
        <div className="pp-section-title">Raw JSON</div>
        <JsonViewer data={data} />
      </div>
    </div>
  )
}
