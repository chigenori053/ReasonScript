import JsonViewer from './JsonViewer.jsx'

const KIND_COLORS = {
  input: '#3b82f6',
  print: '#10b981',
  search: '#f59e0b',
  simulate: '#8b5cf6',
  predict: '#ec4899',
  plan: '#06b6d4',
}

export default function RuntimeOperationsPanel({ data }) {
  if (!data) return null
  const { operations = [], count = 0, by_kind = {}, kinds = [] } = data

  if (count === 0) {
    return (
      <div style={{ padding: '16px', color: '#6b7280', fontFamily: 'monospace', fontStyle: 'italic' }}>
        No runtime operations found in this module.
      </div>
    )
  }

  return (
    <div style={{ padding: '16px', fontFamily: 'monospace' }}>
      <div style={{ color: '#9ca3af', fontSize: '12px', marginBottom: '12px' }}>
        {count} operation(s) · {kinds.length} kind(s)
      </div>
      {kinds.map(kind => (
        <div key={kind} style={{ marginBottom: '16px' }}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px',
          }}>
            <span style={{
              padding: '2px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 600,
              background: KIND_COLORS[kind] || '#374151', color: '#fff',
            }}>{kind}</span>
            <span style={{ color: '#6b7280', fontSize: '11px' }}>{by_kind[kind]?.length ?? 0} call(s)</span>
          </div>
          {(by_kind[kind] || []).map((op, i) => (
            <div key={i} style={{
              background: '#1e1e2e', border: '1px solid #374151',
              borderRadius: '6px', padding: '8px 12px', marginBottom: '4px',
              fontSize: '12px', color: '#d1d5db',
            }}>
              <code>{kind}({op.argument || op.target || ''})</code>
            </div>
          ))}
        </div>
      ))}
    </div>
  )
}
