export default function TypeCoveragePanel({ data }) {
  if (!data) return null
  const { declared = [], inferred = [], unknown = [], total = 0, coverage_pct = 0, has_unknowns } = data

  return (
    <div style={{ padding: '16px', fontFamily: 'monospace' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '16px' }}>
        <Gauge pct={coverage_pct} />
        <div>
          <div style={{ fontSize: '28px', fontWeight: 700, color: pctColor(coverage_pct) }}>
            {coverage_pct}%
          </div>
          <div style={{ color: '#6b7280', fontSize: '12px' }}>Type Coverage ({total} types)</div>
        </div>
      </div>

      <Section title="Declared" items={declared} color="#34d399" />
      <Section title="Inferred" items={inferred} color="#93c5fd" />
      {has_unknowns && <Section title="Unknown" items={unknown} color="#f87171" warn />}
    </div>
  )
}

function pctColor(p) {
  if (p >= 80) return '#34d399'
  if (p >= 50) return '#f59e0b'
  return '#ef4444'
}

function Gauge({ pct }) {
  const r = 30, cx = 36, cy = 36
  const circ = 2 * Math.PI * r
  const offset = circ * (1 - pct / 100)
  return (
    <svg width={72} height={72}>
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="#1f2937" strokeWidth={8} />
      <circle cx={cx} cy={cy} r={r} fill="none"
        stroke={pctColor(pct)} strokeWidth={8}
        strokeDasharray={circ} strokeDashoffset={offset}
        strokeLinecap="round"
        transform={`rotate(-90 ${cx} ${cy})`} />
    </svg>
  )
}

function Section({ title, items, color, warn }) {
  if (items.length === 0) return null
  return (
    <div style={{ marginBottom: '14px' }}>
      <div style={{ color: '#6b7280', fontSize: '11px', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        {title} ({items.length})
        {warn && <span style={{ color: '#ef4444', marginLeft: '6px' }}>⚠</span>}
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
        {items.map((item, i) => (
          <div key={i} style={{
            background: '#1e1e2e', border: `1px solid ${color}44`,
            borderRadius: '4px', padding: '4px 10px', fontSize: '12px',
          }}>
            <span style={{ color }}>{item.name}</span>
            <span style={{ color: '#4b5563', marginLeft: '6px' }}>: {item.type}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
