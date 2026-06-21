import { useState, useEffect, useCallback } from 'react'
import Editor from '@monaco-editor/react'
import Toolbar from './components/Toolbar.jsx'
import TabPanel from './components/TabPanel.jsx'
import Console from './components/Console.jsx'
import './App.css'

const DEFAULT_SOURCE = `// ReasonScript Playground
// サンプルを左上のドロップダウンから読み込むか、ここにコードを書いてください。

module HelloWorld {
  object Start
  object Goal
  constraint SafePath
  transition Move {
    Start -> Goal
  }
  goal Reach
}
`

export default function App() {
  const [source, setSource] = useState(DEFAULT_SOURCE)
  const [examples, setExamples] = useState([])
  const [status, setStatus] = useState('idle') // idle | running | ok | error
  const [results, setResults] = useState(null)
  const [logs, setLogs] = useState([])
  const [activeView, setActiveView] = useState('ast')

  useEffect(() => {
    fetch('/api/examples')
      .then(r => r.json())
      .then(setExamples)
      .catch(() => {})
  }, [])

  const addLog = useCallback((level, text) => {
    const ts = new Date().toLocaleTimeString('ja-JP', { hour12: false })
    setLogs(prev => [...prev, { ts, level, text }])
  }, [])

  const handleValidate = useCallback(async () => {
    setStatus('running')
    addLog('info', 'Validate 開始...')
    try {
      const res = await fetch('/api/validate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source, filename: 'playground.rsn' }),
      })
      const data = await res.json()
      setResults(prev => ({ ...(prev || {}), validate: data, ast: data.ast ?? prev?.ast ?? null }))
      if (data.ok) {
        setStatus('ok')
        addLog('success', 'Validation passed ✓')
      } else {
        setStatus('error')
        data.errors.forEach(e =>
          addLog('error', `[${e.phase}] ${e.line ? `Line ${e.line}: ` : ''}${e.message}`)
        )
      }
    } catch (e) {
      setStatus('error')
      addLog('error', `Network error: ${e.message}`)
    }
  }, [source, addLog])

  const handleRun = useCallback(async () => {
    setStatus('running')
    addLog('info', 'Pipeline 実行開始 (Compile → ExecutionPlan → Simulation → Knowledge)...')
    try {
      const res = await fetch('/api/pipeline', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source, filename: 'playground.rsn' }),
      })
      const data = await res.json()
      if (data.ok) {
        setResults(prev => ({
          ...(prev || {}),
          ast: data.ast,
          reason_irs: data.reason_irs,
          execution_plan: data.execution_plan,
          simulation: data.simulation,
          knowledge: data.knowledge,
        }))
        setStatus('ok')
        const irCount = data.reason_irs?.length ?? 0
        const kCount = data.knowledge?.knowledge_count ?? 0
        const simOk = data.simulation?.success ? '✓' : '✗'
        addLog('success', `Pipeline 完了 — IR ${irCount} module, Sim ${simOk}, Knowledge ${kCount} units`)
        setActiveView('execution_plan')
      } else {
        setResults(prev => ({ ...(prev || {}), compile_error: data }))
        setStatus('error')
        ;(data.errors ?? []).forEach(e =>
          addLog('error', `[${e.phase}] ${e.line ? `Line ${e.line}: ` : ''}${e.message}`)
        )
      }
    } catch (e) {
      setStatus('error')
      addLog('error', `Network error: ${e.message}`)
    }
  }, [source, addLog])

  const handleLoadExample = useCallback((id) => {
    const ex = examples.find(e => e.id === id)
    if (!ex) return
    setSource(ex.source)
    setResults(null)
    setStatus('idle')
    addLog('info', `サンプル読み込み: ${ex.name} (${ex.category})`)
  }, [examples, addLog])

  return (
    <div className="app">
      <Toolbar
        status={status}
        examples={examples}
        onValidate={handleValidate}
        onRun={handleRun}
        onLoadExample={handleLoadExample}
        disabled={status === 'running'}
      />
      <div className="main-pane">
        <div className="editor-pane">
          <div className="pane-header">Editor — playground.rsn</div>
          <div className="editor-wrap">
            <Editor
              defaultLanguage="plaintext"
              value={source}
              onChange={v => setSource(v ?? '')}
              theme="vs-dark"
              options={{
                fontSize: 13,
                fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
                minimap: { enabled: false },
                lineNumbers: 'on',
                scrollBeyondLastLine: false,
                wordWrap: 'off',
                padding: { top: 12 },
                renderLineHighlight: 'line',
              }}
            />
          </div>
        </div>
        <div className="result-pane">
          <TabPanel
            results={results}
            activeView={activeView}
            onChangeView={setActiveView}
          />
        </div>
      </div>
      <Console logs={logs} onClear={() => setLogs([])} />
    </div>
  )
}
