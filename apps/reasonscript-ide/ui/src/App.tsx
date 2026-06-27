import { useState, useCallback, useEffect, useRef } from "react";
import Editor from "@monaco-editor/react";
import type { editor } from "monaco-editor";
import Toolbar from "./components/Toolbar";
import TabPanel from "./components/TabPanel";
import DiagnosticsView from "./views/DiagnosticsView";
import JsonArtifactView from "./views/JsonArtifactView";
import ValidationView from "./views/ValidationView";
import ReasonIRView from "./views/ReasonIRView";
import ExecutionPlanView from "./views/ExecutionPlanView";
import DependencyGraphView from "./views/DependencyGraphView";
import WorkspaceExplorerView from "./views/WorkspaceExplorerView";
import { useProjectStore } from "./state/projectStore";
import { useWorkspaceStore } from "./state/workspaceStore";
import { buildProjectState, exportProjectState } from "./bridge";
import { revealSourceSpan, revealSymbolFallback } from "./editor/sourceNavigation";
import type { ArtifactSelection } from "./types";
import "./App.css";

const DEFAULT_SOURCE = `// ReasonScript IDE
module HelloWorld {
  object Start
  object Goal
  transition Move {
    Start -> Goal
  }
  goal Reach
}
`;

export default function App() {
  const [source, setSource] = useState(DEFAULT_SOURCE);
  const [compilerMode] = useState("normal");
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);
  const store = useProjectStore();
  const wsStore = useWorkspaceStore();

  const handleEditorMount = useCallback((ed: editor.IStandaloneCodeEditor) => {
    editorRef.current = ed;
  }, []);

  // When selectedArtifact changes, navigate to source
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
    console.log("[app] build start", { sourceLength: source.length });
    try {
      const state = await buildProjectState(source, "file:///main.rsn");
      console.log("[app] build result", state);
      store.setProjectState(state);
    } catch (e) {
      console.error("[app] build failed (fatal)", e);
      const message = e instanceof Error ? (e.stack ?? e.message) : String(e);
      store.setBuildStatus("error");
      store.setLastError(message);
    }
  }, [source, store]);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const meta = e.metaKey || e.ctrlKey;
      if (meta && e.key === "b") {
        e.preventDefault();
        runBuild();
      } else if (meta && e.key === "Enter") {
        e.preventDefault();
        runBuild();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [runBuild]);

  const handleExport = useCallback(async () => {
    if (!store.projectState) return;
    await exportProjectState(store.projectState, "project_state.json");
  }, [store.projectState]);

  const handleSelectArtifact = useCallback(
    (sel: ArtifactSelection | null) => {
      store.setSelectedArtifact(sel);
    },
    [store]
  );

  const ps = store.projectState;
  const sel = store.selectedArtifact;

  const rightTabs = [
    {
      id: "diagnostics",
      label: `Diagnostics${store.diagnostics.length > 0 ? ` (${store.diagnostics.length})` : ""}`,
      content: (
        <DiagnosticsView
          diagnostics={store.diagnostics}
          selectedArtifact={sel}
          onSelectArtifact={handleSelectArtifact}
        />
      ),
    },
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
      id: "execution_plan",
      label: "Execution Plan",
      content: (
        <ExecutionPlanView
          data={ps?.execution_plan}
          reasonIr={ps?.reason_ir}
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
      id: "ast",
      label: "Surface AST",
      content: <JsonArtifactView data={ps?.surface_ast} label="Surface AST" />,
    },
    {
      id: "semantic_ast",
      label: "Semantic AST",
      content: <JsonArtifactView data={ps?.semantic_ast} label="Semantic AST" />,
    },
    {
      id: "simulation",
      label: "Simulation",
      content: <JsonArtifactView data={ps?.simulation} label="Simulation" />,
    },
    {
      id: "knowledge",
      label: "Knowledge",
      content: <JsonArtifactView data={ps?.knowledge} label="Knowledge" />,
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
            defaultLanguage="plaintext"
            value={source}
            onChange={(v) => setSource(v ?? "")}
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
          <TabPanel tabs={rightTabs} defaultTab="diagnostics" />
        </div>
      </div>

      {store.lastError && (
        <div className="ide-error-bar">{store.lastError}</div>
      )}
    </div>
  );
}
