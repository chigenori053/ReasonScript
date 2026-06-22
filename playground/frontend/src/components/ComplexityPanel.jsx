const METRICS = [
  { key: 'states', label: 'States', icon: '⬡' },
  { key: 'transitions', label: 'Transitions', icon: '→' },
  { key: 'dependency_count', label: 'Dependency Count', icon: '#' },
  { key: 'dependency_depth', label: 'Dependency Depth', icon: '↓' },
  { key: 'knowledge_units', label: 'Knowledge Units', icon: 'K' },
  { key: 'simulation_depth', label: 'Simulation Depth', icon: '~' },
  { key: 'runtime_operations', label: 'Runtime Operations', icon: '▶' },
  { key: 'goals', label: 'Goals', icon: '◎' },
  { key: 'constraints', label: 'Constraints', icon: '⊢' },
]

export default function ComplexityPanel({ data }) {
  if (!data) return null
  const maxVal = Math.max(...METRICS.map(m => data[m.key] || 0), 1)

  return (
    <div style={{ padding: '16px', fontFamily: 'monospace' }}>
      <div style={{ color: '#9ca3af', fontSize: '12px', marginBottom: '16px' }}>
        Compiler Complexity Report
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {METRICS.map(({ key, label, icon }) => {
          const val = data[key] ?? 0
          const pct = Math.max(4, Math.round(val / maxVal * 100))
          return (
            <div key={key}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px', fontSize: '12px' }}>
                <span style={{ color: '#9ca3af' }}>
                  <span style={{ color: '#6366f1', marginRight: '6px', minWidth: '16px', display: 'inline-block' }}>{icon}</span>
                  {label}
                </span>
                <span style={{ color: '#e5e7eb', fontWeight: 600, minWidth: '32px', textAlign: 'right' }}>{val}</span>
              </div>
              <div style={{ height: '6px', background: '#1f2937', borderRadius: '3px', overflow: 'hidden' }}>
                <div style={{
                  height: '100%', width: `${pct}%`,
                  background: val === 0 ? '#374151' : 'linear-gradient(90deg, #6366f1, #a78bfa)',
                  borderRadius: '3px', transition: 'width 0.3s ease',
                }} />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
