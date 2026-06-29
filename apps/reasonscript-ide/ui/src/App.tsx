import { useState, useCallback, useEffect, useRef, useMemo } from "react";
import Editor from "@monaco-editor/react";
import type { editor } from "monaco-editor";
import type * as Monaco from "monaco-editor";
import Toolbar from "./components/Toolbar";
import TabPanel from "./components/TabPanel";
import JsonArtifactView from "./views/JsonArtifactView";
import ValidationView from "./views/ValidationView";
import ReasonIRView from "./views/ReasonIRView";
import DependencyGraphView from "./views/DependencyGraphView";
import WorkspaceExplorerView from "./views/WorkspaceExplorerView";
// Phase IDE-1
import ModelProjectionView from "./views/ModelProjectionView";
// Phase IDE-2
import PipelineOverviewView from "./views/PipelineOverviewView";
import SourceModelView from "./views/SourceModelView";
import ExecutionPlanFlowView from "./views/ExecutionPlanFlowView";
import SimulationTraceView from "./views/SimulationTraceView";
import KnowledgeEvidenceView from "./views/KnowledgeEvidenceView";
import RuntimeOperationsView from "./views/RuntimeOperationsView";
import DiagnosticsView from "./views/DiagnosticsView";
import { registerReasonScriptLanguage, REASONSCRIPT_LANGUAGE_ID } from "./language/registerReasonScriptLanguage";
// Visualization adapters
import { buildPipelineOverview } from "./visualization/buildPipelineOverview";
import { buildSourceModel } from "./visualization/buildSourceModel";
import { buildExecutionPlanFlow } from "./visualization/buildExecutionPlanFlow";
import { buildSimulationTrace } from "./visualization/buildSimulationTrace";
import { buildKnowledgeEvidence } from "./visualization/buildKnowledgeEvidence";
import { useProjectStore } from "./state/projectStore";
import { useWorkspaceStore } from "./state/workspaceStore";
import { buildProjectState, exportProjectState } from "./bridge";
import { revealSourceSpan, revealSymbolFallback } from "./editor/sourceNavigation";
import type { ArtifactSelection, ArtifactKind } from "./types";
import "./App.css";

// v0.6-C: model is the preferred top-level construct for new code
const DEFAULT_SOURCE = `// ReasonScript IDE
model HelloWorld {
  calculation Answer {
    result = 42
  }
}
`;

export default function App() {
  const [source, setSource] = useState(DEFAULT_SOURCE);
  const [compilerMode] = useState("normal");
  const [activeTab, setActiveTab] = useState("overview");
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);
  const store = useProjectStore();
  const wsStore = useWorkspaceStore();

  const handleEditorBeforeMount = useCallback((monaco: typeof Monaco) => {
    registerReasonScriptLanguage(monaco);
  }, []);

  const handleEditorMount = useCallback((ed: editor.IStandaloneCodeEditor) => {
    editorRef.current = ed;
  }, []);

  // Source navigation on artifact selection
  useEffect(() => {
    const sel = store.selectedArtifact;
    const ed = editorRef.current;
    if (!sel || !ed) return;
    if (sel.span && sel.navigation_mode !== "none") {
      revealSourceSpan(ed, sel.span);
    } else if (
      sel.navigation_mode === "symbol_fallback" &&
      sel.metadata?.symbol_fallback
    ) {
      revealSymbolFallback(ed, String(sel.metadata.symbol_fallback));
    }
  }, [store.selectedArtifact]);

  const runBuild = useCallback(async () => {
    store.setBuildStatus("building");
    store.setLastError(null);
    try {
      const state = await buildProjectState(source, "file:///main.rsn");
      store.setProjectState(state);
    } catch (e) {
      const message = e instanceof Error ? (e.stack ?? e.message) : String(e);
      store.setBuildStatus("error");
      store.setLastError(message);
    }
  }, [source, store]);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const meta = e.metaKey || e.ctrlKey;
      if (meta && e.key === "b") { e.preventDefault(); runBuild(); }
      else if (meta && e.key === "Enter") { e.preventDefault(); runBuild(); }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [runBuild]);

  const handleExport = useCallback(async () => {
    if (!store.projectState) return;
    await exportProjectState(store.projectState, "project_state.json");
  }, [store.projectState]);

  const handleSelectArtifact = useCallback(
    (sel: ArtifactSelection | null) => { store.setSelectedArtifact(sel); },
    [store]
  );

  // Navigate to a tab from Pipeline Overview
  const handlePipelineNavigate = useCallback((_kind: ArtifactKind | null, stageId: string) => {
    const stageToTab: Record<string, string> = {
      source: "source_model",
      surface_ast: "source_model",
      semantic_ast: "ast",
      reason_ir: "reason_ir",
      execution_plan: "execution_plan",
      simulation: "simulation",
      knowledge: "knowledge",
      diagnostics: "diagnostics",
    };
    const target = stageToTab[stageId];
    if (target) setActiveTab(target);
  }, []);

  const ps = store.projectState;
  const sel = store.selectedArtifact;

  // Build view models (memoized)
  const pipelineVm = useMemo(() => buildPipelineOverview(ps), [ps]);
  const sourceModelVm = useMemo(() => buildSourceModel(ps?.surface_ast), [ps?.surface_ast]);
  const executionPlanVm = useMemo(() => buildExecutionPlanFlow(ps?.execution_plan), [ps?.execution_plan]);
  const simulationVm = useMemo(() => buildSimulationTrace(ps?.simulation), [ps?.simulation]);
  const knowledgeVm = useMemo(() => buildKnowledgeEvidence(ps?.knowledge), [ps?.knowledge]);

  const diagCount = store.diagnostics.length;

  const rightTabs = [
    // ── Phase IDE-2 primary views ──────────────────────────────────
    {
      id: "overview",
      label: "Overview",
      content: (
        <PipelineOverviewView
          vm={pipelineVm}
          onNavigate={handlePipelineNavigate}
        />
      ),
    },
    {
      id: "diagnostics",
      label: diagCount > 0 ? `Diagnostics (${diagCount})` : "Diagnostics",
      content: (
        <DiagnosticsView
          diagnostics={store.diagnostics}
          selectedArtifact={sel}
          onSelectArtifact={handleSelectArtifact}
        />
      ),
    },
    {
      id: "execution_plan",
      label: "Execution Plan",
      content: (
        <ExecutionPlanFlowView
          vm={executionPlanVm}
          rawData={ps?.execution_plan}
          selectedArtifact={sel}
          onSelectArtifact={handleSelectArtifact}
        />
      ),
    },
    {
      id: "simulation",
      label: "Simulation",
      content: (
        <SimulationTraceView
          vm={simulationVm}
          rawData={ps?.simulation}
          selectedArtifact={sel}
          onSelectArtifact={handleSelectArtifact}
        />
      ),
    },
    {
      id: "knowledge",
      label: "Knowledge",
      content: (
        <KnowledgeEvidenceView
          vm={knowledgeVm}
          rawData={ps?.knowledge}
          selectedArtifact={sel}
          onSelectArtifact={handleSelectArtifact}
        />
      ),
    },
    {
      id: "source_model",
      label: "Source Model",
      content: <SourceModelView vm={sourceModelVm} />,
    },
    {
      id: "runtime_ops",
      label: "Runtime Ops",
      content: <RuntimeOperationsView simulationVm={simulationVm} />,
    },
    // ── Phase IDE-1 views ──────────────────────────────────────────
    {
      id: "projection",
      label: "Projection",
      content: <ModelProjectionView source={source} />,
    },
    // ── Existing structural views ──────────────────────────────────
    {
      id: "reason_ir",
      label: "Reason IR",
      content: (
        <ReasonIRView
          data={ps?.reason_ir}
          selectedArtifact={sel}
          onSelectArtifact={handleSelectArtifact}
        />
      ),
    },
    {
      id: "validation",
      label: "Validation",
      content: (
        <ValidationView
          data={ps?.validation}
          diagnostics={store.diagnostics}
          selectedArtifact={sel}
          onSelectArtifact={handleSelectArtifact}
        />
      ),
    },
    {
      id: "dependency",
      label: "Dependency",
      content: (
        <DependencyGraphView
          data={(ps?.analyzer as Record<string, unknown> | null)?.dependency_graph ?? null}
          selectedArtifact={sel}
          onSelectArtifact={handleSelectArtifact}
        />
      ),
    },
    // ── Raw JSON fallbacks ─────────────────────────────────────────
    {
      id: "ast",
      label: "Surface AST",
      content: <JsonArtifactView data={ps?.surface_ast} label="Surface AST" />,
    },
    {
      id: "semantic_ast",
      label: "Semantic AST",
      content: <JsonArtifactView data={ps?.semantic_ast} label="Semantic AST" />,
    },
  ];

  return (
    <div className="ide-root">
      <Toolbar
        buildStatus={store.buildStatus}
        compilerMode={compilerMode}
        onBuild={runBuild}
        onRun={runBuild}
        onAnalyze={runBuild}
        onExport={handleExport}
        onCompilerModeChange={() => {}}
      />

      {sel && (
        <div className="ide-selection-bar">
          <span style={{ color: "#6b7280" }}>{sel.kind}</span>
          <span style={{ color: "#e5e7eb", marginLeft: 8 }}>{sel.label}</span>
          {sel.navigation_mode === "none" && (
            <span style={{ color: "#374151", marginLeft: 8, fontSize: 11 }}>
              No source span available
            </span>
          )}
          {sel.navigation_mode === "symbol_fallback" && (
            <span style={{ color: "#6b7280", marginLeft: 8, fontSize: 11 }}>
              ↗ symbol fallback
            </span>
          )}
          <button
            onClick={() => store.setSelectedArtifact(null)}
            style={{
              marginLeft: "auto",
              background: "transparent",
              border: "none",
              color: "#6b7280",
              cursor: "pointer",
              fontSize: 12,
            }}
          >
            ✕
          </button>
        </div>
      )}

      <div className="ide-body">
        <WorkspaceExplorerView
          workspace={wsStore.workspace}
          selectedPath={wsStore.selectedPath}
          expandedPaths={wsStore.expandedPaths}
          onSetWorkspace={wsStore.setWorkspace}
          onSelectPath={wsStore.setSelectedPath}
          onToggleExpanded={wsStore.toggleExpanded}
          onClearWorkspace={wsStore.clearWorkspace}
        />
        <div className="ide-editor-pane">
          <Editor
            height="100%"
            defaultLanguage={REASONSCRIPT_LANGUAGE_ID}
            language={REASONSCRIPT_LANGUAGE_ID}
            value={source}
            onChange={(v) => setSource(v ?? "")}
            beforeMount={handleEditorBeforeMount}
            onMount={handleEditorMount}
            theme="vs-dark"
            options={{
              fontSize: 14,
              minimap: { enabled: false },
              lineNumbers: "on",
              wordWrap: "on",
              scrollBeyondLastLine: false,
              fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
            }}
          />
        </div>

        <div className="ide-right-pane">
          <TabPanel tabs={rightTabs} defaultTab={activeTab} />
        </div>
      </div>

      {store.lastError && (
        <div className="ide-error-bar">{store.lastError}</div>
      )}
    </div>
  );
}
