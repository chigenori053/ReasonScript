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
  const [currentArtifacts, setCurrentArtifacts] = useState(null)
  const [artifactSlots, setArtifactSlots] = useState({ a: null, b: null })
  const [exportPath, setExportPath] = useState('')
  const [importPath, setImportPath] = useState('')
  const [baselinePath, setBaselinePath] = useState('')
  const [compilerMode, setCompilerMode] = useState('normal') // normal | strict | rust_compatible

  const artifactsFromPipeline = useCallback((data) => ({
    ast: data.ast,
    semantic_ast: data.ast,
    reason_ir: data.reason_irs?.length === 1 ? data.reason_irs[0] : { modules: data.reason_irs ?? [] },
    execution_plan: data.execution_plan,
    simulation: data.simulation,
    knowledge: data.knowledge,
    validation: data.validation,
    source: { filename: 'playground.rsn', text: source },
  }), [source])

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
      const validation = {
        schema_version: 'validation-report/0.3',
        ok: data.ok,
        errors: data.errors ?? [],
        tree: {
          name: 'Validation',
          ok: data.ok,
          children: [
            { name: 'Parser', ok: data.ok || data.phase !== 'Parse', children: [] },
            { name: 'Semantic', ok: data.ok, children: [] },
            { name: 'SCV-1', ok: data.ok, children: [] },
            { name: 'Planning', ok: false, children: [] },
            { name: 'Simulation', ok: false, children: [] },
            { name: 'Knowledge', ok: false, children: [] },
          ],
        },
      }
      setResults(prev => ({ ...(prev || {}), validate: data, validation, ast: data.ast ?? prev?.ast ?? null }))
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
        const artifacts = artifactsFromPipeline(data)
        setCurrentArtifacts(artifacts)
        setResults(prev => ({
          ...(prev || {}),
          ast: data.ast,
          reason_irs: data.reason_irs,
          execution_plan: data.execution_plan,
          simulation: data.simulation,
          knowledge: data.knowledge,
          validation: data.validation,
          artifacts,
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
  }, [source, addLog, artifactsFromPipeline])

  const handleExport = useCallback(async () => {
    setStatus('running')
    addLog('info', 'Artifact Export 開始...')
    try {
      const res = await fetch('/api/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source, filename: 'playground.rsn' }),
      })
      const data = await res.json()
      if (data.ok) {
        setCurrentArtifacts(data.artifacts)
        setExportPath(data.path)
        setResults(prev => ({ ...(prev || {}), ...data, artifacts: data.artifacts }))
        setStatus('ok')
        addLog('success', `Artifact Export 完了: ${data.path}`)
      } else {
        setStatus('error')
        ;(data.errors ?? []).forEach(e => addLog('error', `[${e.phase}] ${e.message}`))
      }
    } catch (e) {
      setStatus('error')
      addLog('error', `Network error: ${e.message}`)
    }
  }, [source, addLog])

  const handleImport = useCallback(async (slot) => {
    setStatus('running')
    addLog('info', `Artifact Import 開始 (${slot.toUpperCase()})...`)
    try {
      const res = await fetch('/api/import', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: importPath }),
      })
      const data = await res.json()
      setCurrentArtifacts(data.artifacts)
      setArtifactSlots(prev => ({ ...prev, [slot]: data.artifacts }))
      setResults(prev => ({ ...(prev || {}), ...data, artifacts: data.artifacts }))
      setStatus('ok')
      addLog('success', `Artifact Import 完了: ${data.path}`)
      setActiveView('artifacts')
    } catch (e) {
      setStatus('error')
      addLog('error', `Import error: ${e.message}`)
    }
  }, [importPath, addLog])

  const handleSetSlot = useCallback((slot) => {
    if (!currentArtifacts) {
      addLog('error', '比較対象の Artifact がありません。Run または Import を実行してください。')
      return
    }
    setArtifactSlots(prev => ({ ...prev, [slot]: currentArtifacts }))
    addLog('info', `Artifact ${slot.toUpperCase()} を設定しました`)
  }, [currentArtifacts, addLog])

  const handleCompare = useCallback(async () => {
    setStatus('running')
    addLog('info', 'Pipeline Diff 開始...')
    try {
      const res = await fetch('/api/diff', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ a: artifactSlots.a, b: artifactSlots.b }),
      })
      const data = await res.json()
      setResults(prev => ({ ...(prev || {}), diff: data }))
      setStatus('ok')
      addLog('success', `Pipeline Diff 完了: changed ${data.summary?.changed ?? 0}`)
      setActiveView('diff')
    } catch (e) {
      setStatus('error')
      addLog('error', `Diff error: ${e.message}`)
    }
  }, [artifactSlots, addLog])

  const handleRunAll = useCallback(async () => {
    setStatus('running')
    addLog('info', 'Regression Test Runner 開始...')
    try {
      const res = await fetch('/api/run-all', { method: 'POST' })
      const data = await res.json()
      setResults(prev => ({ ...(prev || {}), regression: data }))
      setStatus(data.ok ? 'ok' : 'error')
      addLog(data.ok ? 'success' : 'error', `Regression 完了: PASS ${data.pass}, FAIL ${data.fail}`)
    } catch (e) {
      setStatus('error')
      addLog('error', `Run All error: ${e.message}`)
    }
  }, [addLog])

  const handleSaveBaseline = useCallback(async () => {
    setStatus('running')
    addLog('info', 'Baseline Snapshot 保存開始...')
    try {
      const res = await fetch('/api/baseline', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source, filename: 'playground.rsn' }),
      })
      const data = await res.json()
      if (data.ok) {
        setBaselinePath(data.path)
        setResults(prev => ({ ...(prev || {}), baseline_path: data.path }))
        setStatus('ok')
        addLog('success', `Baseline 保存完了: ${data.path}`)
      } else {
        setStatus('error')
        ;(data.errors ?? []).forEach(e => addLog('error', `[${e.phase}] ${e.message}`))
      }
    } catch (e) {
      setStatus('error')
      addLog('error', `Baseline error: ${e.message}`)
    }
  }, [source, addLog])

  const handleAnalyze = useCallback(async () => {
    setStatus('running')
    addLog('info', `Analyze 開始 (mode: ${compilerMode})...`)
    try {
      const res = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source, filename: 'playground.rsn', compiler_mode: compilerMode }),
      })
      const data = await res.json()
      if (data.ok) {
        setResults(prev => ({ ...(prev || {}), analysis: data.analysis, ast: data.ast ?? prev?.ast }))
        setStatus('ok')
        const q = data.analysis?.quality?.overall_pct ?? '—'
        addLog('success', `Analyze 完了 — Quality Score: ${q}%`)
        setActiveView('quality')
      } else {
        setStatus('error')
        ;(data.errors ?? []).forEach(e => addLog('error', `[${e.phase}] ${e.message}`))
      }
    } catch (e) {
      setStatus('error')
      addLog('error', `Analyze error: ${e.message}`)
    }
  }, [source, compilerMode, addLog])

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
        onAnalyze={handleAnalyze}
        onLoadExample={handleLoadExample}
        disabled={status === 'running'}
        compilerMode={compilerMode}
        onCompilerModeChange={setCompilerMode}
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
            controls={{
              disabled: status === 'running',
              exportPath,
              importPath,
              baselinePath,
              slots: artifactSlots,
              diff: results?.diff,
              regression: results?.regression,
              onImportPathChange: setImportPath,
              onExport: handleExport,
              onImport: handleImport,
              onSetSlot: handleSetSlot,
              onCompare: handleCompare,
              onRunAll: handleRunAll,
              onSaveBaseline: handleSaveBaseline,
              compilerMode,
            }}
          />
        </div>
      </div>
      <Console logs={logs} onClear={() => setLogs([])} />
    </div>
  )
}
