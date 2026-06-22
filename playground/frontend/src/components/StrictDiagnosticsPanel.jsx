const CODE_COLORS = {
  'STRICT-001': '#f59e0b',
  'STRICT-002': '#ef4444',
  'RUST-001': '#ec4899',
}

export default function StrictDiagnosticsPanel({ data, mode }) {
  if (!data) return null
  const { diagnostics = [], count = 0 } = data
  const currentMode = mode || data.mode || 'normal'

  if (currentMode === 'normal') {
    return (
      <div style={{ padding: '16px', color: '#6b7280', fontFamily: 'monospace' }}>
        Strict Mode is disabled. Enable it in the toolbar to run additional checks.
      </div>
    )
  }

  return (
    <div style={{ padding: '16px', fontFamily: 'monospace' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '16px' }}>
        <ModeTag mode={currentMode} />
        <span style={{ color: count === 0 ? '#34d399' : '#f87171', fontSize: '12px' }}>
          {count === 0 ? '✓ No diagnostics' : `${count} diagnostic(s)`}
        </span>
      </div>
      {diagnostics.map((d, i) => (
        <div key={i} style={{
          background: '#1e1e2e',
          border: `1px solid ${CODE_COLORS[d.code] || '#374151'}55`,
          borderRadius: '6px', padding: '10px 14px', marginBottom: '8px',
        }}>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '4px' }}>
            <span style={{
              padding: '1px 6px', borderRadius: '4px', fontSize: '10px', fontWeight: 700,
              background: CODE_COLORS[d.code] || '#374151',
              color: '#fff',
            }}>{d.code}</span>
            <span style={{ color: '#9ca3af', fontSize: '11px', textTransform: 'uppercase' }}>{d.kind}</span>
          </div>
          <div style={{ color: '#e5e7eb', fontSize: '13px' }}>{d.message}</div>
          {d.name && <div style={{ color: '#a78bfa', fontSize: '11px', marginTop: '4px' }}>→ {d.name}</div>}
          {d.state && <div style={{ color: '#a78bfa', fontSize: '11px', marginTop: '4px' }}>→ {d.state}</div>}
        </div>
      ))}
    </div>
  )
}

function ModeTag({ mode }) {
  const colors = {
    strict: { bg: '#7c3aed', text: 'Strict' },
    rust_compatible: { bg: '#dc2626', text: 'Rust-Compatible' },
    normal: { bg: '#374151', text: 'Normal' },
  }
  const c = colors[mode] || colors.normal
  return (
    <span style={{
      background: c.bg, color: '#fff',
      padding: '2px 10px', borderRadius: '4px', fontSize: '11px', fontWeight: 700,
    }}>{c.text} Mode</span>
  )
}
