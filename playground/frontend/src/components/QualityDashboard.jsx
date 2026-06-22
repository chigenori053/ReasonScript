export default function QualityDashboard({ data }) {
  if (!data) return null
  const { compiler_version, metrics = [], overall_pct = 0 } = data

  return (
    <div style={{ padding: '16px', fontFamily: 'monospace' }}>
      <div style={{ marginBottom: '20px' }}>
        <div style={{ color: '#a78bfa', fontWeight: 700, fontSize: '15px', marginBottom: '4px' }}>
          {compiler_version || 'ReasonScript v0.1 Alpha'}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <OverallGauge pct={overall_pct} />
          <div>
            <div style={{ fontSize: '32px', fontWeight: 800, color: pctColor(overall_pct) }}>
              {overall_pct}%
            </div>
            <div style={{ color: '#6b7280', fontSize: '12px' }}>Rust Compatibility Score</div>
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {metrics.map(({ name, pct }) => (
          <MetricRow key={name} name={name} pct={pct} />
        ))}
      </div>
    </div>
  )
}

function MetricRow({ name, pct }) {
  const color = pctColor(pct)
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
      <div style={{ minWidth: '200px', color: '#9ca3af', fontSize: '13px' }}>{name}</div>
      <div style={{ flex: 1, height: '8px', background: '#1f2937', borderRadius: '4px', overflow: 'hidden' }}>
        <div style={{
          height: '100%',
          width: `${pct}%`,
          background: color,
          borderRadius: '4px',
          transition: 'width 0.4s ease',
        }} />
      </div>
      <div style={{ minWidth: '44px', textAlign: 'right', color, fontWeight: 700, fontSize: '13px' }}>
        {pct}%
      </div>
    </div>
  )
}

function OverallGauge({ pct }) {
  const r = 38, cx = 44, cy = 44
  const circ = 2 * Math.PI * r
  const offset = circ * (1 - pct / 100)
  const color = pctColor(pct)
  return (
    <svg width={88} height={88}>
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="#1f2937" strokeWidth={10} />
      <circle cx={cx} cy={cy} r={r} fill="none"
        stroke={color} strokeWidth={10}
        strokeDasharray={circ} strokeDashoffset={offset}
        strokeLinecap="round"
        transform={`rotate(-90 ${cx} ${cy})`} />
    </svg>
  )
}

function pctColor(p) {
  if (p >= 80) return '#34d399'
  if (p >= 50) return '#f59e0b'
  return '#ef4444'
}
