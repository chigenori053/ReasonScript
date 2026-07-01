import { useState, useCallback, useEffect, useRef, useMemo } from "react";
import Editor from "@monaco-editor/react";
import type { editor } from "monaco-editor";
import type * as Monaco from "monaco-editor";
import Toolbar from "./components/Toolbar";
import TabPanel from "./components/TabPanel";
import WorkspaceExplorerView from "./views/WorkspaceExplorerView";
// Phase IDE-2
import ExecutionPlanFlowView from "./views/ExecutionPlanFlowView";
import SimulationTraceView from "./views/SimulationTraceView";
import KnowledgeEvidenceView from "./views/KnowledgeEvidenceView";
import {
  ArtifactsInspectorView,
  BottomToolWindow,
  StandardOverviewView,
} from "./views/StandardLayoutViews";
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
  const [activeInspectorTab, setActiveInspectorTab] = useState("overview");
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
      source: "artifacts",
      surface_ast: "artifacts",
      semantic_ast: "artifacts",
      reason_ir: "artifacts",
      execution_plan: "plan",
      simulation: "simulation",
      knowledge: "knowledge",
      diagnostics: "overview",
    };
    const target = stageToTab[stageId];
    if (target) setActiveInspectorTab(target);
  }, []);

  const ps = store.projectState;
  const sel = store.selectedArtifact;

  // Build view models (memoized)
  const pipelineVm = useMemo(() => buildPipelineOverview(ps), [ps]);
  const sourceModelVm = useMemo(() => buildSourceModel(ps?.surface_ast), [ps?.surface_ast]);
  const executionPlanVm = useMemo(() => buildExecutionPlanFlow(ps?.execution_plan), [ps?.execution_plan]);
  const simulationVm = useMemo(() => buildSimulationTrace(ps?.simulation), [ps?.simulation]);
  const knowledgeVm = useMemo(() => buildKnowledgeEvidence(ps?.knowledge), [ps?.knowledge]);

  const rightInspectorTabs = [
    {
      id: "overview",
      label: "Overview",
      content: (
        <StandardOverviewView
          projectState={ps}
          source={source}
          compilerMode={compilerMode}
          buildStatus={store.buildStatus}
          pipelineVm={pipelineVm}
          knowledgeVm={knowledgeVm}
          onNavigate={(stageId) => handlePipelineNavigate(null, stageId)}
        />
      ),
    },
    {
      id: "plan",
      label: "Plan",
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
      id: "artifacts",
      label: "Artifacts",
      content: (
        <ArtifactsInspectorView
          projectState={ps}
          sourceModelVm={sourceModelVm}
          selectedArtifact={sel}
          onSelectArtifact={handleSelectArtifact}
        />
      ),
    },
  ];

  return (
    <div className="ide-root">
      <Toolbar
        buildStatus={store.buildStatus}
        compilerMode={compilerMode}
        projectName={wsStore.workspace?.root_name ?? ps?.workspace?.project_name ?? "ReasonScript"}
        selectedFile={wsStore.selectedPath ?? ps?.metadata?.source_filename ?? "temporary source"}
        dirty={source !== (ps?.source_files?.[0]?.text ?? source)}
        onRun={runBuild}
        onAnalyze={runBuild}
        onValidate={runBuild}
        onAudit={runBuild}
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
        <div className="ide-main-pane">
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
          <BottomToolWindow
            diagnostics={store.diagnostics}
            simulationVm={simulationVm}
            projectState={ps}
            lastError={store.lastError}
            selectedArtifact={sel}
            onSelectArtifact={handleSelectArtifact}
          />
        </div>

        <div className="ide-right-pane">
          <TabPanel
            tabs={rightInspectorTabs}
            activeTab={activeInspectorTab}
            onActiveTabChange={setActiveInspectorTab}
          />
        </div>
      </div>

      {store.lastError && (
        <div className="ide-error-bar">{store.lastError}</div>
      )}
    </div>
  );
}
