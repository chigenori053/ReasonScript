import { useState, useEffect, useCallback } from 'react'
import Editor from '@monaco-editor/react'
import Toolbar from './components/Toolbar.jsx'
import TabPanel from './components/TabPanel.jsx'
import Console from './components/Console.jsx'
import WorkspaceExplorer from './components/WorkspaceExplorer.jsx'
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

  // --- Phase 3: workspace file editing state ---
  const [workspaceRoot, setWorkspaceRoot] = useState(null)
  const [workspaceFiles, setWorkspaceFiles] = useState([])
  const [workspaceScanStatus, setWorkspaceScanStatus] = useState(null)
  const [workspaceError, setWorkspaceError] = useState(null)
  const [workspaceLoading, setWorkspaceLoading] = useState(false)
  const [selectedFile, setSelectedFile] = useState(null)
  // selectedFile: { relativePath, content, savedContent, version, readOnly, missing }
  const [analyzeResultsByFile, setAnalyzeResultsByFile] = useState({})
  // analyzeResultsByFile: { [relativePath]: { result, analyzedContent } }

  const selectedDirty = !!selectedFile && selectedFile.content !== selectedFile.savedContent
  const selectedCache = selectedFile ? analyzeResultsByFile[selectedFile.relativePath] : null
  const selectedStale = !!(selectedFile && selectedCache && selectedCache.analyzedContent !== selectedFile.content)

  const artifactsFromPipeline = useCallback((data) => ({
    ast: data.ast,
    semantic_ast: data.semantic_ast,
    reason_ir: data.reason_irs?.length === 1 ? data.reason_irs[0] : { modules: data.reason_irs ?? [] },
    execution_plan: data.execution_plan,
    simulation: data.simulation,
    knowledge: data.knowledge,
    diagnostics: data.diagnostics ?? [],
    projection_summary: data.projection_summary ?? null,
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
          pipeline: data.pipeline,
          views: data.views,
          ast: data.ast,
          semantic_ast: data.semantic_ast,
          reason_irs: data.reason_irs,
          execution_plan: data.execution_plan,
          simulation: data.simulation,
          knowledge: data.knowledge,
          diagnostics: data.diagnostics ?? [],
          projection_summary: data.projection_summary,
          validation: data.validation,
          artifacts,
        }))
        setStatus('ok')
        const irCount = data.reason_irs?.length ?? 0
        const kCount = data.knowledge?.knowledge_count ?? 0
        const simOk = data.simulation?.success ? '✓' : '✗'
        addLog('success', `Pipeline 完了 — IR ${irCount} module, Sim ${simOk}, Knowledge ${kCount} units`)
        setActiveView('pipeline')
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
    const analyzedSource = selectedFile ? selectedFile.content : source
    const sourceContext = selectedFile
      ? { workspace_root: workspaceRoot, relative_path: selectedFile.relativePath, dirty: selectedDirty }
      : undefined
    try {
      const res = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source: analyzedSource,
          filename: selectedFile ? selectedFile.relativePath : 'playground.rsn',
          compiler_mode: compilerMode,
          ...(sourceContext ? { source_context: sourceContext } : {}),
        }),
      })
      const data = await res.json()
      const nextResults = {
        pipeline: data.pipeline,
        views: data.views,
        analysis: data.analysis,
        ast: data.ast,
        semantic_ast: data.semantic_ast,
        reason_irs: data.reason_irs,
        execution_plan: data.execution_plan,
        simulation: data.simulation,
        knowledge: data.knowledge,
        diagnostics: data.diagnostics ?? data.errors ?? [],
        projection_summary: data.projection_summary,
        validation: data.validation,
        artifacts: data.artifacts,
        source_context: data.source_context,
      }
      setCurrentArtifacts(data.artifacts ?? null)
      setResults(prev => ({ ...(prev || {}), ...nextResults, ast: data.ast ?? prev?.ast }))
      if (selectedFile) {
        setAnalyzeResultsByFile(prev => ({
          ...prev,
          [selectedFile.relativePath]: { result: nextResults, analyzedContent: analyzedSource },
        }))
      }
      if (data.ok) {
        setStatus('ok')
        const q = data.analysis?.quality?.overall_pct ?? '—'
        addLog('success', `Analyze 完了 — Quality Score: ${q}%`)
      } else {
        setStatus('error')
        ;(data.diagnostics ?? data.errors ?? []).forEach(e => addLog('error', `[${e.stage ?? e.phase}] ${e.message}`))
      }
      setActiveView('pipeline')
    } catch (e) {
      setStatus('error')
      addLog('error', `Analyze error: ${e.message}`)
    }
  }, [source, compilerMode, addLog, selectedFile, workspaceRoot, selectedDirty])

  const handleOpenWorkspace = useCallback(async (rootPath) => {
    setWorkspaceLoading(true)
    setWorkspaceError(null)
    addLog('info', `Workspace を開いています: ${rootPath}`)
    try {
      const res = await fetch('/api/workspace/list', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ workspace_root: rootPath }),
      })
      const data = await res.json()
      if (data.ok) {
        setWorkspaceRoot(data.root)
        setWorkspaceFiles(data.files)
        setWorkspaceScanStatus(data.scan_status)
        setSelectedFile(null)
        addLog('success', `Workspace を開きました: ${data.root}`)
      } else {
        setWorkspaceError(data.error?.message || 'workspace を開けませんでした')
        addLog('error', `Workspace error: ${data.error?.message}`)
      }
    } catch (e) {
      setWorkspaceError(e.message)
      addLog('error', `Workspace error: ${e.message}`)
    } finally {
      setWorkspaceLoading(false)
    }
  }, [addLog])

  const handleRefreshWorkspace = useCallback(async () => {
    if (!workspaceRoot) return
    setWorkspaceLoading(true)
    try {
      const res = await fetch('/api/workspace/list', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ workspace_root: workspaceRoot }),
      })
      const data = await res.json()
      if (data.ok) {
        setWorkspaceFiles(data.files)
        setWorkspaceScanStatus(data.scan_status)
        if (selectedFile) {
          const stillExists = (nodes) => nodes.some(n =>
            n.relative_path === selectedFile.relativePath || (n.children && stillExists(n.children))
          )
          if (!stillExists(data.files)) {
            setSelectedFile(prev => (prev ? { ...prev, missing: true } : prev))
          }
        }
      }
    } catch (e) {
      addLog('error', `Refresh error: ${e.message}`)
    } finally {
      setWorkspaceLoading(false)
    }
  }, [workspaceRoot, selectedFile, addLog])

  const handleSelectFile = useCallback(async (relativePath) => {
    if (selectedDirty) {
      const proceed = window.confirm(
        `未保存の変更があります (${selectedFile.relativePath})。破棄して切り替えますか?`
      )
      if (!proceed) return
    }
    addLog('info', `ファイルを開いています: ${relativePath}`)
    try {
      const res = await fetch('/api/workspace/read', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ workspace_root: workspaceRoot, relative_path: relativePath }),
      })
      const data = await res.json()
      if (data.ok) {
        setSelectedFile({
          relativePath: data.relative_path,
          content: data.content,
          savedContent: data.content,
          version: data.version,
          readOnly: data.read_only,
          missing: false,
        })
        const cached = analyzeResultsByFile[relativePath]
        setResults(cached ? cached.result : null)
        setStatus('idle')
        addLog('success', `ファイルを開きました: ${relativePath}`)
      } else {
        addLog('error', `ファイルを読み込めません: ${data.error?.message}`)
      }
    } catch (e) {
      addLog('error', `File read error: ${e.message}`)
    }
  }, [workspaceRoot, selectedDirty, selectedFile, analyzeResultsByFile, addLog])

  const handleSaveFile = useCallback(async () => {
    if (!selectedFile) return
    addLog('info', `保存しています: ${selectedFile.relativePath}`)
    try {
      const res = await fetch('/api/workspace/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workspace_root: workspaceRoot,
          relative_path: selectedFile.relativePath,
          content: selectedFile.content,
          expected_version: selectedFile.version,
        }),
      })
      const data = await res.json()
      if (data.ok) {
        setSelectedFile(prev => (prev ? { ...prev, savedContent: prev.content, version: data.version } : prev))
        addLog('success', `保存しました: ${selectedFile.relativePath}`)
      } else {
        addLog('error', `Save error: [${data.error?.code}] ${data.error?.message}`)
      }
    } catch (e) {
      addLog('error', `Save error: ${e.message}`)
    }
  }, [selectedFile, workspaceRoot, addLog])

  const handleEditorChange = useCallback((value) => {
    if (selectedFile) {
      setSelectedFile(prev => (prev ? { ...prev, content: value ?? '' } : prev))
    } else {
      setSource(value ?? '')
    }
  }, [selectedFile])

  const handleAudit = useCallback(async () => {
    setStatus('running')
    addLog('info', 'Language Integration Audit 開始...')
    try {
      const res = await fetch('/api/language-audit')
      const data = await res.json()
      setResults(prev => ({ ...(prev || {}), audit: data.matrix }))
      setStatus(data.ok ? 'ok' : 'error')
      const summary = data.matrix?.summary
      addLog(data.ok ? 'success' : 'error', `Audit 完了: CONNECTED ${summary?.connected ?? 0}/${summary?.total ?? 0}`)
      setActiveView('audit')
    } catch (e) {
      setStatus('error')
      addLog('error', `Audit error: ${e.message}`)
    }
  }, [addLog])

  const handleExportAudit = useCallback(async () => {
    setStatus('running')
    addLog('info', 'Language Audit Report Export 開始...')
    try {
      const res = await fetch('/api/language-audit/export', { method: 'POST' })
      const data = await res.json()
      setResults(prev => ({ ...(prev || {}), audit: data.matrix, audit_files: data.files }))
      setStatus(data.ok ? 'ok' : 'error')
      addLog(data.ok ? 'success' : 'error', `Audit Report Export 完了`)
      setActiveView('audit')
    } catch (e) {
      setStatus('error')
      addLog('error', `Audit export error: ${e.message}`)
    }
  }, [addLog])

  const handleLoadExample = useCallback((id) => {
    const ex = examples.find(e => e.id === id)
    if (!ex) return
    setSelectedFile(null)
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
        onAudit={handleAudit}
        onLoadExample={handleLoadExample}
        disabled={status === 'running'}
        compilerMode={compilerMode}
        onCompilerModeChange={setCompilerMode}
      />
      <div className="main-pane">
        <WorkspaceExplorer
          root={workspaceRoot}
          files={workspaceFiles}
          scanStatus={workspaceScanStatus}
          selectedPath={selectedFile?.relativePath ?? null}
          missingSelected={!!selectedFile?.missing}
          loading={workspaceLoading}
          error={workspaceError}
          onOpenWorkspace={handleOpenWorkspace}
          onRefresh={handleRefreshWorkspace}
          onSelectFile={handleSelectFile}
        />
        <div className="editor-pane">
          <div className="pane-header editor-pane-header">
            {selectedFile ? (
              <>
                <span className="editor-filename">{selectedFile.relativePath}</span>
                {selectedDirty && <span className="editor-dirty-dot" title="unsaved changes">●</span>}
                {selectedFile.readOnly && <span className="editor-badge">read-only</span>}
                {selectedFile.missing && <span className="editor-badge editor-badge-warn">missing</span>}
                {selectedStale && <span className="editor-badge editor-badge-warn">stale analysis</span>}
                <span className="editor-header-spacer" />
                <button
                  className="editor-save-btn"
                  onClick={handleSaveFile}
                  disabled={!selectedDirty || selectedFile.readOnly || selectedFile.missing}
                >
                  Save
                </button>
              </>
            ) : (
              'Editor — playground.rsn (temporary)'
            )}
          </div>
          <div className="editor-wrap">
            <Editor
              defaultLanguage="plaintext"
              value={selectedFile ? selectedFile.content : source}
              onChange={handleEditorChange}
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
                readOnly: !!(selectedFile?.readOnly || selectedFile?.missing),
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
              onRunAudit: handleAudit,
              onExportAudit: handleExportAudit,
              compilerMode,
            }}
          />
        </div>
      </div>
      <Console logs={logs} onClear={() => setLogs([])} />
    </div>
  )
}
