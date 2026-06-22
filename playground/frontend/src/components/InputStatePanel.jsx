import JsonViewer from './JsonViewer.jsx'

export default function InputStatePanel({ data }) {
  if (!data) return null
  const { input_states = [], count = 0 } = data

  if (count === 0) {
    return (
      <div style={{ padding: '16px', color: '#6b7280', fontFamily: 'monospace', fontStyle: 'italic' }}>
        No input() operations found. Use <code style={{ color: '#3b82f6' }}>input(Name)</code> to declare runtime inputs.
      </div>
    )
  }

  return (
    <div style={{ padding: '16px', fontFamily: 'monospace' }}>
      <div style={{ color: '#9ca3af', fontSize: '12px', marginBottom: '12px' }}>
        {count} InputState(s)
      </div>
      {input_states.map((s, i) => (
        <div key={i} style={{
          background: '#1e1e2e', border: '1px solid #1d4ed8',
          borderRadius: '6px', padding: '12px 16px', marginBottom: '10px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
            <span style={{
              background: '#1d4ed8', color: '#fff', padding: '1px 8px',
              borderRadius: '4px', fontSize: '10px', fontWeight: 600,
            }}>INPUT</span>
            <span style={{ color: '#93c5fd', fontWeight: 600 }}>{s.state_id}</span>
          </div>
          <JsonViewer data={s} />
        </div>
      ))}
    </div>
  )
}
