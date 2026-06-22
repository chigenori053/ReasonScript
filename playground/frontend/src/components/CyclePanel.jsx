export default function CyclePanel({ data }) {
  if (!data) return null
  const { ok, has_cycle, cycle_nodes = [], errors = [] } = data

  return (
    <div style={{ padding: '16px', fontFamily: 'monospace' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '16px' }}>
        <span style={{
          fontSize: '20px', width: '32px', height: '32px', borderRadius: '50%',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: ok ? '#064e3b' : '#450a0a', color: ok ? '#34d399' : '#f87171',
        }}>{ok ? '✓' : '✗'}</span>
        <div>
          <div style={{ color: ok ? '#34d399' : '#f87171', fontWeight: 700 }}>
            {ok ? 'No Cycles Detected' : 'Dependency Cycle Detected'}
          </div>
          <div style={{ color: '#6b7280', fontSize: '12px' }}>
            {ok ? 'Dependency graph is acyclic' : `CAL-030: ${cycle_nodes.length} node(s) in cycle`}
          </div>
        </div>
      </div>

      {has_cycle && (
        <>
          <div style={{ color: '#9ca3af', fontSize: '12px', marginBottom: '8px' }}>Cycle Nodes:</div>
          <div style={{
            display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '16px',
          }}>
            {cycle_nodes.map((n, i) => (
              <span key={i} style={{
                background: '#450a0a', border: '1px solid #ef4444', color: '#fca5a5',
                padding: '4px 10px', borderRadius: '4px', fontSize: '12px',
              }}>{n}</span>
            ))}
          </div>
          <div style={{ background: '#1e1e2e', borderRadius: '8px', padding: '16px', textAlign: 'center' }}>
            <div style={{ color: '#f87171', fontSize: '24px', lineHeight: '1.8' }}>
              {cycle_nodes[0] || 'A'}<br />↓<br />{cycle_nodes[1] || 'B'}<br />↑<br />
              <span style={{ color: '#6b7280' }}>└───</span>
            </div>
          </div>
          {errors.map((e, i) => (
            <div key={i} style={{
              marginTop: '12px', background: '#450a0a', border: '1px solid #ef4444',
              borderRadius: '6px', padding: '10px 14px', fontSize: '12px', color: '#fca5a5',
            }}>
              [{e.code}] {e.message}
            </div>
          ))}
        </>
      )}
    </div>
  )
}
