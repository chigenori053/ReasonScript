export default function ExhaustivenessPanel({ data }) {
  if (!data) return null
  const { all_states = [], handled = [], missing = [], is_exhaustive, coverage_pct = 0 } = data

  return (
    <div style={{ padding: '16px', fontFamily: 'monospace' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
        <span style={{
          fontSize: '22px', width: '36px', height: '36px', borderRadius: '50%',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: is_exhaustive ? '#064e3b' : '#450a0a',
          color: is_exhaustive ? '#34d399' : '#f87171',
        }}>{is_exhaustive ? '✓' : '✗'}</span>
        <div>
          <div style={{ color: is_exhaustive ? '#34d399' : '#f87171', fontWeight: 700 }}>
            {is_exhaustive ? 'Exhaustive' : `Non-exhaustive — ${missing.length} unhandled state(s)`}
          </div>
          <div style={{ color: '#6b7280', fontSize: '12px' }}>{coverage_pct}% coverage ({all_states.length} states)</div>
        </div>
      </div>

      <StateSection title="Handled" items={handled} color="#34d399" />
      {missing.length > 0 && <StateSection title="Missing" items={missing} color="#f87171" />}
    </div>
  )
}

function StateSection({ title, items, color }) {
  if (items.length === 0) return null
  return (
    <div style={{ marginBottom: '14px' }}>
      <div style={{ color: '#6b7280', fontSize: '11px', marginBottom: '6px', textTransform: 'uppercase' }}>
        {title} ({items.length})
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
        {items.map((s, i) => (
          <span key={i} style={{
            background: color + '11', border: `1px solid ${color}55`,
            color, padding: '4px 10px', borderRadius: '4px', fontSize: '12px',
          }}>{s}</span>
        ))}
      </div>
    </div>
  )
}
