import './ValidationExplorer.css'

function ValidationNode({ node, depth = 0 }) {
  if (!node) return null
  const children = node.children ?? []
  return (
    <div className="validation-node">
      <div className="validation-row" style={{ paddingLeft: `${depth * 18 + 10}px` }}>
        <span className={`validation-mark ${node.ok ? 'ok' : 'fail'}`}>{node.ok ? '✓' : '✗'}</span>
        <span className="validation-name">{node.name}</span>
        {node.details?.phase && <span className="validation-phase">{node.details.phase}</span>}
      </div>
      {children.map((child, index) => (
        <ValidationNode key={`${child.name}-${index}`} node={child} depth={depth + 1} />
      ))}
    </div>
  )
}

export default function ValidationExplorer({ data }) {
  if (!data) {
    return <div className="panel-empty">Validation 結果がありません</div>
  }
  return (
    <div className="validation-explorer">
      <div className="validation-summary">
        <span className={`validation-status ${data.ok ? 'ok' : 'fail'}`}>
          {data.ok ? 'PASS' : 'FAIL'}
        </span>
        <span>{data.schema_version ?? 'validation-report/0.3'}</span>
      </div>
      <ValidationNode node={data.tree} />
      {data.errors?.length > 0 && (
        <div className="validation-errors">
          {data.errors.map((error, index) => (
            <div key={index} className="validation-error">
              [{error.phase}] {error.line ? `Line ${error.line}: ` : ''}{error.message}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
