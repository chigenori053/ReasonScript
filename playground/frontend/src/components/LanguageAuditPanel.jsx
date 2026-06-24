import './ValidationPanels.css'

export default function LanguageAuditPanel({ data, onRunAudit, onExportAudit, disabled }) {
  const matrix = data?.matrix ?? data
  const features = matrix?.features ?? []
  const summary = matrix?.summary

  return (
    <div className="validation-panel">
      <section className="tool-section">
        <div className="tool-section-head">
          <h3>Language Integration Audit</h3>
          <div className="segmented">
            <button onClick={onRunAudit} disabled={disabled}>Run</button>
            <button onClick={onExportAudit} disabled={disabled || !matrix}>Export</button>
          </div>
        </div>
        {summary && (
          <div className="diff-grid">
            <div className="metric pass"><span>CONNECTED</span><strong>{summary.connected}</strong></div>
            <div className="metric"><span>PARTIAL</span><strong>{summary.partial}</strong></div>
            <div className="metric fail"><span>MISSING</span><strong>{summary.missing}</strong></div>
            <div className="metric"><span>Coverage</span><strong>{summary.connected_pct}%</strong></div>
          </div>
        )}
      </section>

      <section className="tool-section">
        {features.length === 0 ? (
          <div className="tool-note">Run を実行すると compiler/playground coverage matrix が表示されます。</div>
        ) : (
          <div className="result-list">
            {features.map(feature => (
              <div key={feature.feature} className={`result-row ${feature.status === 'CONNECTED' ? 'pass' : 'fail'}`}>
                <span>{feature.feature}</span>
                <strong>{feature.status}</strong>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
