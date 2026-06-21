import { useState } from 'react'
import './ValidationPanels.css'

export default function ExportPanel({ exportPath, importPath, onImportPathChange, onExport, onImport, disabled }) {
  const [slot, setSlot] = useState('a')
  return (
    <div className="validation-panel">
      <section className="tool-section">
        <div className="tool-section-head">
          <h3>Artifact Export</h3>
          <button onClick={onExport} disabled={disabled}>Export</button>
        </div>
        <div className="tool-note">
          AST, Semantic AST, Reason IR, ExecutionPlan, Simulation, Knowledge, Validation を保存します。
        </div>
        {exportPath && <div className="path-box">{exportPath}</div>}
      </section>

      <section className="tool-section">
        <div className="tool-section-head">
          <h3>Artifact Import</h3>
          <div className="segmented">
            <button className={slot === 'a' ? 'active' : ''} onClick={() => setSlot('a')}>A</button>
            <button className={slot === 'b' ? 'active' : ''} onClick={() => setSlot('b')}>B</button>
          </div>
        </div>
        <div className="inline-form">
          <input
            value={importPath}
            onChange={event => onImportPathChange(event.target.value)}
            placeholder="playground/exports/sample_001"
          />
          <button onClick={() => onImport(slot)} disabled={disabled || !importPath.trim()}>Import</button>
        </div>
      </section>
    </div>
  )
}
