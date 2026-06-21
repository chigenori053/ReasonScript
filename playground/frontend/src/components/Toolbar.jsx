import './Toolbar.css'

const STATUS_ICON = {
  idle: null,
  running: '⏳',
  ok: '✓',
  error: '✗',
}
const STATUS_CLASS = {
  idle: '',
  running: 'running',
  ok: 'ok',
  error: 'error',
}

export default function Toolbar({ status, examples, onValidate, onRun, onLoadExample, disabled }) {
  const categories = [...new Set(examples.map(e => e.category))]

  return (
    <div className="toolbar">
      <span className="toolbar-brand">
        <span className="brand-rs">RS</span> ReasonScript Playground
      </span>

      <div className="toolbar-sep" />

      <label className="toolbar-label">Examples</label>
      <select
        onChange={e => { if (e.target.value) { onLoadExample(e.target.value); e.target.value = '' } }}
        defaultValue=""
      >
        <option value="" disabled>Select sample…</option>
        {categories.map(cat => (
          <optgroup key={cat} label={cat.charAt(0).toUpperCase() + cat.slice(1)}>
            {examples.filter(e => e.category === cat).map(ex => (
              <option key={ex.id} value={ex.id}>{ex.name}</option>
            ))}
          </optgroup>
        ))}
      </select>

      <div className="toolbar-spacer" />

      <button
        className="btn-validate"
        onClick={onValidate}
        disabled={disabled}
        title="Parse → AST → Semantic Validation"
      >
        Validate
      </button>
      <button
        className="btn-run"
        onClick={onRun}
        disabled={disabled}
        title="Parse → AST → Compile → Reason IR"
      >
        ▶ Run
      </button>

      {status !== 'idle' && (
        <span className={`status-badge ${STATUS_CLASS[status]}`}>
          {STATUS_ICON[status]} {status === 'running' ? 'Processing…' : status === 'ok' ? 'Success' : 'Failed'}
        </span>
      )}
    </div>
  )
}
