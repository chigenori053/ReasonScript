import JsonViewer from './JsonViewer.jsx'

function GraphNode({ label, depth, x, y }) {
  return (
    <g transform={`translate(${x},${y})`}>
      <rect x={-50} y={-16} width={100} height={32} rx={6}
        fill="#1e1e2e" stroke="#6366f1" strokeWidth={1.5} />
      <text textAnchor="middle" dominantBaseline="middle"
        fill="#e5e7eb" fontSize={11} fontFamily="monospace">
        {label.length > 12 ? label.slice(0, 11) + '…' : label}
      </text>
    </g>
  )
}

export default function DependencyGraphPanel({ data }) {
  if (!data) return null
  const { nodes = [], dependencies = [], topological_order = [], depth = {}, has_cycle, cycle_nodes = [] } = data

  const [view, setView] = React.useState('graph')

  // Layout: group by depth level
  const maxDepth = Math.max(...Object.values(depth), 0)
  const byDepth = {}
  for (const [node, d] of Object.entries(depth)) {
    ;(byDepth[d] = byDepth[d] || []).push(node)
  }

  const nodePos = {}
  const SVG_W = 600
  const LEVEL_H = 80
  const SVG_H = (maxDepth + 2) * LEVEL_H + 40

  for (let d = 0; d <= maxDepth; d++) {
    const row = byDepth[d] || []
    row.forEach((n, i) => {
      const x = SVG_W / (row.length + 1) * (i + 1)
      const y = 40 + d * LEVEL_H
      nodePos[n] = { x, y }
    })
  }

  return (
    <div style={{ padding: '16px', fontFamily: 'monospace' }}>
      <div style={{ display: 'flex', gap: '8px', marginBottom: '12px', alignItems: 'center' }}>
        <span style={{ color: '#9ca3af', fontSize: '12px' }}>
          {nodes.length} nodes · {dependencies.length} edges
          {has_cycle && <span style={{ color: '#ef4444', marginLeft: '8px' }}>⚠ Cycle Detected</span>}
        </span>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: '4px' }}>
          {['graph', 'json'].map(v => (
            <button key={v} onClick={() => setView(v)} style={{
              padding: '2px 10px', fontSize: '11px', borderRadius: '4px', border: 'none', cursor: 'pointer',
              background: view === v ? '#6366f1' : '#374151', color: '#e5e7eb',
            }}>{v.toUpperCase()}</button>
          ))}
        </div>
      </div>

      {view === 'graph' && (
        <svg width="100%" viewBox={`0 0 ${SVG_W} ${SVG_H}`}
          style={{ background: '#0f0f1a', borderRadius: '8px', border: '1px solid #1f2937' }}>
          <defs>
            <marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
              <path d="M0,0 L0,6 L8,3 z" fill="#6b7280" />
            </marker>
          </defs>
          {dependencies.map(([src, tgt], i) => {
            const s = nodePos[src]
            const t = nodePos[tgt]
            if (!s || !t) return null
            const isCycle = has_cycle && cycle_nodes.includes(src) && cycle_nodes.includes(tgt)
            return (
              <line key={i}
                x1={s.x} y1={s.y + 16} x2={t.x} y2={t.y - 16}
                stroke={isCycle ? '#ef4444' : '#4b5563'}
                strokeWidth={1.5}
                markerEnd="url(#arrow)" />
            )
          })}
          {Object.entries(nodePos).map(([label, { x, y }]) => (
            <GraphNode key={label} label={label} x={x} y={y} />
          ))}
        </svg>
      )}

      {view === 'json' && (
        <JsonViewer data={{ dependencies, topological_order, depth }} />
      )}

      <div style={{ marginTop: '12px', color: '#6b7280', fontSize: '11px' }}>
        Topological order: {topological_order.join(' → ') || '—'}
      </div>
    </div>
  )
}

import React from 'react'
