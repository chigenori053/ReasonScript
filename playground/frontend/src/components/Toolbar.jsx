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

const MODE_LABELS = {
  normal: 'Normal',
  strict: 'Strict',
  rust_compatible: 'Rust-Compat',
}

export default function Toolbar({
  status, examples, onValidate, onRun, onAnalyze, onLoadExample, disabled,
  compilerMode, onCompilerModeChange,
}) {
  const categories = [...new Set(examples.map(e => e.category))]

  return (
    <div className="toolbar">
      <span className="toolbar-brand">
        <span className="brand-rs">RS</span> Playground <span style={{ color: '#6366f1', fontSize: '11px', marginLeft: '4px' }}>v0.5</span>
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

      <div className="toolbar-sep" />

      <label className="toolbar-label">Mode</label>
      <select
        value={compilerMode}
        onChange={e => onCompilerModeChange?.(e.target.value)}
        style={{ fontSize: '12px' }}
        title="Compiler verification mode"
      >
        {Object.entries(MODE_LABELS).map(([val, label]) => (
          <option key={val} value={val}>{label}</option>
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
        title="Parse → AST → Compile → Reason IR → Pipeline"
      >
        ▶ Run
      </button>
      <button
        className="btn-analyze"
        onClick={onAnalyze}
        disabled={disabled}
        title="Run full v0.5 analysis: Dependency Graph, Ownership, Determinism, Quality…"
        style={{
          background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
          color: '#fff',
          border: 'none',
          borderRadius: '6px',
          padding: '5px 14px',
          fontSize: '13px',
          fontWeight: 600,
          cursor: disabled ? 'not-allowed' : 'pointer',
          opacity: disabled ? 0.6 : 1,
        }}
      >
        ⚡ Analyze
      </button>

      {status !== 'idle' && (
        <span className={`status-badge ${STATUS_CLASS[status]}`}>
          {STATUS_ICON[status]} {status === 'running' ? 'Processing…' : status === 'ok' ? 'Success' : 'Failed'}
        </span>
      )}
    </div>
  )
}
