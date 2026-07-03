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
import type { ArtifactSelection, ArtifactKind, FileNode, WorkspaceScanStatus, WorkspaceState } from "./types";
import { getPlatformAdapter, setAnalyzeArtifactSource, validateNormalizedRelativePath } from "./platform";
import type { WorkspaceFileNode } from "./platform";
import "./App.css";

// v0.6-C: model is the preferred top-level construct for new code
const DEFAULT_SOURCE = `// ReasonScript IDE
model HelloWorld {
  calculation Answer {
    result = 42
  }
}
`;

function scanStatusToWorkspaceState(status: { status: string; truncated: boolean }): WorkspaceScanStatus {
  if (status.truncated || status.status === "warning") return "partial";
  if (status.status === "success") return "complete";
  return "failed";
}

function toFileNode(node: WorkspaceFileNode): FileNode {
  const relativePath = node.relativePath;
  return {
    name: node.name,
    path: relativePath,
    relative_path: relativePath,
    kind: node.kind,
    extension: node.extension ?? (node.kind === "file" ? node.name.split(".").pop() ?? null : null),
    children: (node.children ?? []).map(toFileNode),
    is_ignored: node.isIgnored ?? node.is_ignored ?? node.supported === false,
    metadata: {
      supported: node.supported,
      dirty: node.dirty,
      missing: node.missing,
      read_only: node.readOnly,
    },
  };
}

function workspaceFromAdapterResult(root: string, files: WorkspaceFileNode[], scanStatus: { status: string; truncated: boolean }): WorkspaceState {
  const parts = root.split("/").filter(Boolean);
  return {
    schema_version: "reasonscript-workspace/0.1",
    root_path: root,
    root_name: parts.length > 0 ? parts[parts.length - 1] : root,
    files: files.map(toFileNode),
    selected_path: null,
    active_file_path: null,
    ignored_patterns: [],
    scan_status: scanStatusToWorkspaceState(scanStatus),
    metadata: { platform_adapter: "browser" },
  };
}

export default function App() {
  const [source, setSource] = useState(DEFAULT_SOURCE);
  const [savedSource, setSavedSource] = useState(DEFAULT_SOURCE);
  const [selectedVersion, setSelectedVersion] = useState<string | undefined>(undefined);
  const [selectedReadOnly, setSelectedReadOnly] = useState(false);
  const [compilerMode] = useState("normal");
  const [activeInspectorTab, setActiveInspectorTab] = useState("overview");
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);
  const store = useProjectStore();
  const wsStore = useWorkspaceStore();
  const platform = useMemo(() => getPlatformAdapter(), []);

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
      let sourceContext;
      if (wsStore.workspace && wsStore.selectedPath) {
        const pathResult = validateNormalizedRelativePath(wsStore.selectedPath);
        if (!pathResult.ok) {
          store.setBuildStatus("error");
          store.setLastError(pathResult.error.message);
          return;
        }
        sourceContext = {
          workspace_root: wsStore.workspace.root_path,
          relative_path: pathResult.relativePath,
          dirty: source !== savedSource,
        };
      }

      const state = await buildProjectState(
        source,
        wsStore.selectedPath ? `file:///${wsStore.selectedPath}` : "file:///main.rsn",
        sourceContext
      );
      store.setProjectState(state);
      setAnalyzeArtifactSource(state);
    } catch (e) {
      const message = e instanceof Error ? (e.stack ?? e.message) : String(e);
      store.setBuildStatus("error");
      store.setLastError(message);
    }
  }, [savedSource, source, store, wsStore.selectedPath, wsStore.workspace]);

  const handleOpenWorkspace = useCallback(async (rootPath: string) => {
    const result = await platform.workspace.listWorkspace({ workspaceRoot: rootPath });
    if (!result.ok) throw new Error(result.error.message);
    wsStore.setWorkspace(workspaceFromAdapterResult(result.root, result.files, result.scanStatus));
    wsStore.setSelectedPath(null);
    wsStore.setActiveFilePath(null);
  }, [platform, wsStore]);

  const handleRefreshWorkspace = useCallback(async () => {
    if (!wsStore.workspace) return;
    const result = await platform.workspace.listWorkspace({ workspaceRoot: wsStore.workspace.root_path });
    if (!result.ok) throw new Error(result.error.message);
    wsStore.setWorkspace(workspaceFromAdapterResult(result.root, result.files, result.scanStatus));
  }, [platform, wsStore]);

  const handleSelectWorkspacePath = useCallback(async (relativePath: string | null) => {
    if (!relativePath || !wsStore.workspace) {
      wsStore.setSelectedPath(null);
      wsStore.setActiveFilePath(null);
      return;
    }

    const pathResult = validateNormalizedRelativePath(relativePath);
    if (!pathResult.ok) {
      store.setLastError(pathResult.error.message);
      return;
    }

    const result = await platform.workspace.readFile({
      workspaceRoot: wsStore.workspace.root_path,
      relativePath: pathResult.relativePath,
    });
    if (!result.ok) {
      store.setLastError(result.error.message);
      return;
    }

    const nextSource = result.content ?? "";
    wsStore.setSelectedPath(pathResult.relativePath);
    wsStore.setActiveFilePath(pathResult.relativePath);
    setSource(nextSource);
    setSavedSource(nextSource);
    setSelectedVersion(result.version);
    setSelectedReadOnly(Boolean(result.readOnly));
    store.setLastError(null);
  }, [platform, store, wsStore]);

  const saveCurrentFile = useCallback(async () => {
    if (!wsStore.workspace || !wsStore.selectedPath) return;
    if (selectedReadOnly) {
      store.setLastError("Selected file is read-only.");
      return;
    }
    const pathResult = validateNormalizedRelativePath(wsStore.selectedPath);
    if (!pathResult.ok) {
      store.setLastError(pathResult.error.message);
      return;
    }
    const result = await platform.workspace.saveFile({
      workspaceRoot: wsStore.workspace.root_path,
      relativePath: pathResult.relativePath,
      content: source,
      expectedVersion: selectedVersion,
    });
    if (!result.ok) {
      store.setLastError(result.error.message);
      return;
    }
    setSelectedVersion(result.version);
    setSavedSource(source);
    store.setLastError(null);
  }, [platform, selectedReadOnly, selectedVersion, source, store, wsStore.selectedPath, wsStore.workspace]);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const meta = e.metaKey || e.ctrlKey;
      if (meta && e.key === "b") { e.preventDefault(); runBuild(); }
      else if (meta && e.key === "Enter") { e.preventDefault(); runBuild(); }
      else if (meta && e.key.toLowerCase() === "s") { e.preventDefault(); saveCurrentFile(); }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [runBuild, saveCurrentFile]);

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
        dirty={wsStore.selectedPath ? source !== savedSource : source !== (ps?.source_files?.[0]?.text ?? source)}
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
          onSelectPath={handleSelectWorkspacePath}
          onToggleExpanded={wsStore.toggleExpanded}
          onClearWorkspace={wsStore.clearWorkspace}
          onOpenWorkspace={handleOpenWorkspace}
          onRefreshWorkspace={handleRefreshWorkspace}
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
