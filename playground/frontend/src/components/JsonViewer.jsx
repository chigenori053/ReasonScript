import { useState } from 'react'
import './JsonViewer.css'

function JsonNode({ data, depth = 0, keyName = null }) {
  const [collapsed, setCollapsed] = useState(depth > 2)

  if (data === null || data === undefined) {
    return <span className="jv-null">null</span>
  }
  if (typeof data === 'boolean') {
    return <span className="jv-bool">{String(data)}</span>
  }
  if (typeof data === 'number') {
    return <span className="jv-num">{data}</span>
  }
  if (typeof data === 'string') {
    return <span className="jv-str">"{data}"</span>
  }

  const isArray = Array.isArray(data)
  const entries = isArray ? data.map((v, i) => [i, v]) : Object.entries(data)

  if (entries.length === 0) {
    return <span className="jv-empty">{isArray ? '[]' : '{}'}</span>
  }

  const open = isArray ? '[' : '{'
  const close = isArray ? ']' : '}'
  const count = entries.length

  return (
    <span className="jv-node">
      <button className="jv-toggle" onClick={() => setCollapsed(c => !c)}>
        {collapsed ? '▶' : '▼'}
      </button>
      <span className="jv-brace">{open}</span>
      {collapsed ? (
        <span className="jv-collapsed" onClick={() => setCollapsed(false)}>
          {count} {count === 1 ? 'item' : 'items'}
        </span>
      ) : (
        <span className="jv-children">
          {entries.map(([k, v]) => (
            <div key={k} className="jv-row" style={{ paddingLeft: 20 }}>
              {!isArray && <span className="jv-key">"{k}"</span>}
              {!isArray && <span className="jv-colon">: </span>}
              <JsonNode data={v} depth={depth + 1} keyName={k} />
              <span className="jv-comma">,</span>
            </div>
          ))}
        </span>
      )}
      <span className="jv-brace">{close}</span>
    </span>
  )
}

export default function JsonViewer({ data }) {
  const [raw, setRaw] = useState(false)
  const json = JSON.stringify(data, null, 2)

  return (
    <div className="json-viewer">
      <div className="jv-toolbar">
        <button className="jv-mode-btn" onClick={() => setRaw(r => !r)}>
          {raw ? 'Tree' : 'Raw'}
        </button>
        <button
          className="jv-mode-btn"
          onClick={() => navigator.clipboard?.writeText(json)}
          title="Copy JSON"
        >
          Copy
        </button>
      </div>
      {raw ? (
        <pre className="jv-raw">{json}</pre>
      ) : (
        <div className="jv-tree">
          <JsonNode data={data} depth={0} />
        </div>
      )}
    </div>
  )
}
