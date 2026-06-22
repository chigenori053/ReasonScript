export default function CalculationPanel({ data }) {
  if (!data) return null
  const { calculations = [], count = 0 } = data

  if (count === 0) {
    return (
      <div style={{ padding: '16px', color: '#6b7280', fontFamily: 'monospace', fontStyle: 'italic' }}>
        No calculations found.
      </div>
    )
  }

  return (
    <div style={{ padding: '16px', fontFamily: 'monospace' }}>
      <div style={{ color: '#9ca3af', fontSize: '12px', marginBottom: '12px' }}>
        {count} calculation(s)
      </div>
      {calculations.map((calc, i) => (
        <div key={i} style={{
          background: '#1e1e2e', border: '1px solid #374151',
          borderRadius: '8px', padding: '14px 16px', marginBottom: '12px',
        }}>
          <div style={{ color: '#a78bfa', fontWeight: 700, marginBottom: '10px', fontSize: '14px' }}>
            {calc.name}
          </div>
          <div style={{ display: 'grid', gap: '6px', fontSize: '12px' }}>
            <Row label="Inputs" value={calc.inputs.join(', ') || '—'} color="#93c5fd" />
            <Row label="Dependencies" value={calc.dependencies.join(', ') || '—'} color="#6b7280" />
            <Row label="Transitions" value={calc.transitions.join(', ') || '—'} color="#6b7280" />
            <Row label="Output" value={calc.output_state} color="#34d399" />
          </div>
        </div>
      ))}
    </div>
  )
}

function Row({ label, value, color }) {
  return (
    <div style={{ display: 'flex', gap: '8px' }}>
      <span style={{ color: '#6b7280', minWidth: '100px' }}>{label}:</span>
      <span style={{ color: color || '#e5e7eb' }}>{value}</span>
    </div>
  )
}
