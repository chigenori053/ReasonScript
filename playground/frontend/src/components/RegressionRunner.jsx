import './ValidationPanels.css'

export default function RegressionRunner({ result, onRunAll, disabled }) {
  return (
    <div className="validation-panel">
      <section className="tool-section">
        <div className="tool-section-head">
          <h3>Regression Test Runner</h3>
          <button onClick={onRunAll} disabled={disabled}>Run All Tests</button>
        </div>
        {result && (
          <>
            <div className="diff-grid">
              <div className="metric pass"><span>PASS</span><strong>{result.pass}</strong></div>
              <div className="metric fail"><span>FAIL</span><strong>{result.fail}</strong></div>
              <div className="metric"><span>Total</span><strong>{result.results?.length ?? 0}</strong></div>
            </div>
            <div className="result-list">
              {(result.results ?? []).map(item => (
                <div key={item.file} className={`result-row ${item.status.toLowerCase()}`}>
                  <span>{item.file}</span>
                  <strong>{item.status}</strong>
                </div>
              ))}
            </div>
          </>
        )}
      </section>
    </div>
  )
}
