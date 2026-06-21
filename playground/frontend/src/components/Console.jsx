import './Console.css'

const LEVEL_CLASS = { info: 'log-info', success: 'log-success', error: 'log-error', warn: 'log-warn' }
const LEVEL_PREFIX = { info: '›', success: '✓', error: '✗', warn: '⚠' }

export default function Console({ logs, onClear }) {
  return (
    <div className="console-panel">
      <div className="console-header">
        <span>Console</span>
        <span className="console-count">{logs.length} entries</span>
        <button className="console-clear" onClick={onClear}>Clear</button>
      </div>
      <div className="console-body">
        {logs.length === 0 ? (
          <span className="console-empty">Validate または Run を実行すると出力が表示されます</span>
        ) : (
          logs.map((log, i) => (
            <div key={i} className={`log-line ${LEVEL_CLASS[log.level] ?? ''}`}>
              <span className="log-ts">{log.ts}</span>
              <span className="log-prefix">{LEVEL_PREFIX[log.level] ?? '·'}</span>
              <span className="log-msg">{log.text}</span>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
