export default function DeterminismPanel({ data }) {
  if (!data) return null
  const {
    deterministic_transitions = [],
    input_boundaries = [],
    non_deterministic_sources = [],
    deterministic_after_boundary,
    projection_stable,
    knowledge_reproducible,
    overall_deterministic,
  } = data

  return (
    <div style={{ padding: '16px', fontFamily: 'monospace' }}>
      <div style={{ display: 'flex', gap: '10px', marginBottom: '20px', flexWrap: 'wrap' }}>
        <Badge label="Overall" ok={overall_deterministic} />
        <Badge label="After Boundary" ok={deterministic_after_boundary} />
        <Badge label="Projection Stable" ok={projection_stable} />
        <Badge label="Knowledge Reproducible" ok={knowledge_reproducible} />
      </div>

      {input_boundaries.length > 0 && (
        <Section title="External Input Boundaries">
          {input_boundaries.map((b, i) => (
            <Row key={i} icon="⬛" color="#3b82f6" label={`input(${b.argument || ''})`}
              sub="Non-deterministic source — boundary" />
          ))}
        </Section>
      )}

      {non_deterministic_sources.length > 0 && (
        <Section title="Non-deterministic Sources">
          {non_deterministic_sources.map((s, i) => (
            <Row key={i} icon="⚠" color="#f59e0b" label={s.source} sub={s.reason} />
          ))}
        </Section>
      )}

      {deterministic_transitions.length > 0 && (
        <Section title={`Deterministic Transitions (${deterministic_transitions.length})`}>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
            {deterministic_transitions.map((t, i) => (
              <span key={i} style={{
                background: '#064e3b', border: '1px solid #10b98144',
                color: '#34d399', padding: '3px 8px', borderRadius: '4px', fontSize: '11px',
              }}>{t}</span>
            ))}
          </div>
        </Section>
      )}
    </div>
  )
}

function Badge({ label, ok }) {
  return (
    <div style={{
      padding: '4px 12px', borderRadius: '6px', fontSize: '12px',
      background: ok ? '#064e3b' : '#450a0a',
      border: `1px solid ${ok ? '#10b981' : '#ef4444'}44`,
      color: ok ? '#34d399' : '#f87171',
    }}>
      {ok ? '✓' : '✗'} {label}
    </div>
  )
}

function Section({ title, children }) {
  return (
    <div style={{ marginBottom: '16px' }}>
      <div style={{ color: '#6b7280', fontSize: '11px', textTransform: 'uppercase', marginBottom: '8px', letterSpacing: '0.05em' }}>
        {title}
      </div>
      {children}
    </div>
  )
}

function Row({ icon, color, label, sub }) {
  return (
    <div style={{
      display: 'flex', gap: '10px', alignItems: 'flex-start',
      background: '#1e1e2e', border: `1px solid ${color}33`,
      borderRadius: '6px', padding: '8px 12px', marginBottom: '6px',
    }}>
      <span style={{ color, fontSize: '14px' }}>{icon}</span>
      <div>
        <div style={{ color: '#e5e7eb', fontSize: '13px', fontFamily: 'monospace' }}>{label}</div>
        {sub && <div style={{ color: '#6b7280', fontSize: '11px', marginTop: '2px' }}>{sub}</div>}
      </div>
    </div>
  )
}
