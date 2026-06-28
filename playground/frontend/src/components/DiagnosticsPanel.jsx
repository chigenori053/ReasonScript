import './DiagnosticsPanel.css'

const LAYER_LABELS = {
  L1: 'L1 Syntax',
  L2: 'L2 Semantic',
  L4: 'L4 Planning',
  L5: 'L5 Simulation',
  L6: 'L6 Knowledge',
  L7: 'L7 Projection',
}

function layerLabel(diagnostic) {
  const layer = diagnostic.layer
  if (layer && LAYER_LABELS[layer]) return LAYER_LABELS[layer]
  if (layer) return layer
  if (diagnostic.phase === 'Parse') return LAYER_LABELS.L1
  if (diagnostic.phase === 'Compile' || diagnostic.phase === 'Validation') return LAYER_LABELS.L2
  return 'Unclassified'
}

export default function DiagnosticsPanel({ data }) {
  const diagnostics = Array.isArray(data) ? data : []
  if (diagnostics.length === 0) {
    return <div className="diagnostics-empty">No diagnostics.</div>
  }
  const grouped = diagnostics.reduce((groups, diagnostic) => {
    const label = layerLabel(diagnostic)
    return { ...groups, [label]: [...(groups[label] ?? []), diagnostic] }
  }, {})

  return (
    <div className="diagnostics-panel">
      {Object.entries(grouped).map(([label, items]) => (
        <section className="diagnostics-layer" key={label}>
          <div className="diagnostics-layer-title">{label}</div>
          {items.map((diagnostic, index) => (
            <div className={`diagnostic-row ${diagnostic.severity ?? 'error'}`} key={`${diagnostic.code ?? diagnostic.phase ?? label}-${index}`}>
              <div className="diagnostic-meta">
                <span>{diagnostic.severity ?? 'error'}</span>
                {(diagnostic.code || diagnostic.phase) && <code>{diagnostic.code ?? diagnostic.phase}</code>}
              </div>
              <div className="diagnostic-message">
                {diagnostic.line ? `Line ${diagnostic.line}: ` : ''}{diagnostic.message}
              </div>
            </div>
          ))}
        </section>
      ))}
    </div>
  )
}
