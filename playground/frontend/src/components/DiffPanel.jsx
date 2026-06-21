import JsonViewer from './JsonViewer.jsx'
import './ValidationPanels.css'

function TraceLine({ label, trace }) {
  return (
    <div className="diff-trace">
      <div className="diff-label">{label}</div>
      <div className="trace-path">{trace?.length ? trace.join(' → ') : 'No trace'}</div>
    </div>
  )
}

export default function DiffPanel({ diff, slots, onSetSlot, onCompare, disabled }) {
  return (
    <div className="validation-panel">
      <section className="tool-section">
        <div className="tool-section-head">
          <h3>Compare A ↔ B</h3>
          <div className="button-row">
            <button onClick={() => onSetSlot('a')} disabled={disabled}>Set A</button>
            <button onClick={() => onSetSlot('b')} disabled={disabled}>Set B</button>
            <button onClick={onCompare} disabled={disabled || !slots.a || !slots.b}>Compare</button>
          </div>
        </div>
        <div className="slot-grid">
          <div className={slots.a ? 'slot ready' : 'slot'}>A {slots.a ? 'READY' : 'EMPTY'}</div>
          <div className={slots.b ? 'slot ready' : 'slot'}>B {slots.b ? 'READY' : 'EMPTY'}</div>
        </div>
      </section>

      {diff && (
        <section className="tool-section">
          <div className="diff-grid">
            <div className="metric">
              <span>Distance OLD</span>
              <strong>{diff.execution_plan?.distance?.old ?? '-'}</strong>
            </div>
            <div className="metric">
              <span>Distance NEW</span>
              <strong>{diff.execution_plan?.distance?.new ?? '-'}</strong>
            </div>
            <div className="metric">
              <span>Changed</span>
              <strong>{diff.summary?.changed ?? 0}</strong>
            </div>
          </div>
          <TraceLine label="OLD Trace" trace={diff.simulation?.old_trace} />
          <TraceLine label="NEW Trace" trace={diff.simulation?.new_trace} />

          <div className="knowledge-diff">
            <h4>Added Knowledge</h4>
            {(diff.knowledge?.added ?? []).map(item => <div key={item} className="added">+ {item}</div>)}
            {(diff.knowledge?.added ?? []).length === 0 && <div className="muted">No additions</div>}
            <h4>Removed Knowledge</h4>
            {(diff.knowledge?.removed ?? []).map(item => <div key={item} className="removed">- {item}</div>)}
            {(diff.knowledge?.removed ?? []).length === 0 && <div className="muted">No removals</div>}
          </div>
          <details>
            <summary>Raw diff</summary>
            <JsonViewer data={diff} />
          </details>
        </section>
      )}
    </div>
  )
}
