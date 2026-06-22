const KIND_ICON = {
  InputState: { icon: '▶', color: '#3b82f6', bg: '#1d3b6e' },
  Transition: { icon: '→', color: '#10b981', bg: '#064e3b' },
  OutputEvent: { icon: '◀', color: '#f59e0b', bg: '#451a03' },
  start: { icon: '●', color: '#6366f1', bg: '#2e1065' },
  unknown: { icon: '?', color: '#6b7280', bg: '#1f2937' },
}

export default function RuntimeTracePanel({ data }) {
  if (!data) return null
  const { trace = [], step_count = 0, success, final_state } = data

  return (
    <div style={{ padding: '16px', fontFamily: 'monospace' }}>
      <div style={{ display: 'flex', gap: '12px', marginBottom: '14px', alignItems: 'center' }}>
        <span style={{ color: '#9ca3af', fontSize: '12px' }}>{step_count} step(s)</span>
        {final_state && (
          <span style={{ color: '#6b7280', fontSize: '12px' }}>→ <span style={{ color: '#a78bfa' }}>{final_state}</span></span>
        )}
        <span style={{
          marginLeft: 'auto', padding: '2px 10px', borderRadius: '12px', fontSize: '11px',
          background: success ? '#064e3b' : '#450a0a',
          color: success ? '#34d399' : '#f87171',
        }}>{success ? '✓ Success' : '✗ Failed'}</span>
      </div>

      <div style={{ position: 'relative' }}>
        {trace.map((step, i) => {
          const style = KIND_ICON[step.kind] || KIND_ICON.unknown
          return (
            <div key={i} style={{ display: 'flex', gap: '12px', marginBottom: '4px', alignItems: 'flex-start' }}>
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: '24px' }}>
                <div style={{
                  width: '24px', height: '24px', borderRadius: '50%',
                  background: style.bg, color: style.color,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: '12px', fontWeight: 700, flexShrink: 0,
                }}>{style.icon}</div>
                {i < trace.length - 1 && (
                  <div style={{ width: '1px', height: '20px', background: '#374151' }} />
                )}
              </div>
              <div style={{
                background: '#1e1e2e', border: `1px solid ${style.bg}`,
                borderRadius: '6px', padding: '6px 10px', fontSize: '12px',
                flex: 1, marginBottom: '4px',
              }}>
                <span style={{ color: style.color, fontWeight: 600 }}>{step.kind}</span>
                {step.state && <span style={{ color: '#9ca3af', marginLeft: '8px' }}>{step.state}</span>}
                {step.transition && (
                  <span style={{ color: '#6b7280', marginLeft: '8px', fontSize: '11px' }}>
                    ({step.transition.source} → {step.transition.target})
                  </span>
                )}
                {step.rendered_value && (
                  <span style={{ color: '#fcd34d', marginLeft: '8px' }}>"{step.rendered_value}"</span>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
