import JsonViewer from './JsonViewer.jsx'

export default function OutputPanel({ data }) {
  if (!data) return null
  const { events = [], event_count = 0, has_output } = data

  return (
    <div style={{ padding: '16px', fontFamily: 'monospace' }}>
      <div style={{ marginBottom: '12px', color: '#9ca3af', fontSize: '12px' }}>
        Runtime IO Output — {event_count} event(s)
      </div>
      {!has_output && (
        <div style={{ color: '#6b7280', fontStyle: 'italic' }}>
          No output events. Add <code style={{ color: '#a78bfa' }}>print()</code> calls to generate output.
        </div>
      )}
      {events.map((ev, i) => (
        <div key={i} style={{ marginBottom: '16px' }}>
          <div style={{
            background: '#1e1e2e',
            border: '1px solid #374151',
            borderRadius: '6px',
            padding: '12px 16px',
          }}>
            <div style={{ color: '#e5e7eb', fontSize: '16px', marginBottom: '8px' }}>
              {ev.rendered_value}
            </div>
            <details style={{ cursor: 'pointer' }}>
              <summary style={{ color: '#6b7280', fontSize: '11px', userSelect: 'none' }}>
                Expanded View
              </summary>
              <div style={{ marginTop: '8px' }}>
                <JsonViewer data={{
                  output_id: ev.output_id,
                  projection: ev.projection,
                  rendered_value: ev.rendered_value,
                }} />
              </div>
            </details>
          </div>
        </div>
      ))}
    </div>
  )
}
