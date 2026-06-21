import './ValidationPanels.css'

export default function BaselinePanel({ baselinePath, onSaveBaseline, disabled }) {
  return (
    <div className="validation-panel">
      <section className="tool-section">
        <div className="tool-section-head">
          <h3>Baseline Snapshot</h3>
          <button onClick={onSaveBaseline} disabled={disabled}>Save Baseline</button>
        </div>
        <div className="tool-note">
          ExecutionPlan, Simulation, Knowledge をリリース基準として baseline/ 配下に保存します。
        </div>
        {baselinePath && <div className="path-box">{baselinePath}</div>}
      </section>
    </div>
  )
}
