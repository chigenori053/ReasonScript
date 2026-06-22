export default function OwnershipPanel({ data }) {
  if (!data) return null
  const { entries = [], count = 0 } = data

  return (
    <div style={{ padding: '16px', fontFamily: 'monospace' }}>
      <div style={{ color: '#9ca3af', fontSize: '12px', marginBottom: '12px' }}>
        {count} state(s) analyzed
      </div>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid #374151', color: '#6b7280' }}>
            <th style={{ textAlign: 'left', padding: '6px 8px' }}>State</th>
            <th style={{ textAlign: 'left', padding: '6px 8px' }}>Producer</th>
            <th style={{ textAlign: 'left', padding: '6px 8px' }}>Consumer</th>
            <th style={{ textAlign: 'left', padding: '6px 8px' }}>Candidate</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((e, i) => (
            <tr key={i} style={{ borderBottom: '1px solid #1f2937' }}>
              <td style={{ padding: '6px 8px', color: '#a78bfa', fontWeight: 600 }}>{e.state}</td>
              <td style={{ padding: '6px 8px', color: '#34d399' }}>{e.producer || '—'}</td>
              <td style={{ padding: '6px 8px', color: '#f59e0b' }}>{e.consumer || '—'}</td>
              <td style={{ padding: '6px 8px' }}>
                {e.borrow_candidate && <Tag label="Borrow" color="#3b82f6" />}
                {e.move_candidate && <Tag label="Move" color="#10b981" />}
                {e.clone_candidate && <Tag label="Clone" color="#8b5cf6" />}
                {!e.borrow_candidate && !e.move_candidate && !e.clone_candidate && (
                  <span style={{ color: '#4b5563' }}>—</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Tag({ label, color }) {
  return (
    <span style={{
      background: color + '22', border: `1px solid ${color}`, color,
      padding: '1px 6px', borderRadius: '4px', fontSize: '10px', marginRight: '4px',
    }}>{label}</span>
  )
}
