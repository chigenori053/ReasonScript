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
import {
  artifactWorkflowIssuesAsPlatformDiagnostics,
  artifactWorkflowStateForProject,
  buildArtifactWorkflowViewModel,
  type ArtifactOperationKind,
  type ArtifactOperationLog,
  type ArtifactOperationStatus,
  type ArtifactWorkflowViewModel,
  type ExportArtifactResult,
  type ImportArtifactResult,
  type DiffArtifactResult,
} from "./viewModels/artifactWorkflow";
import {
  buildDiagnosticsAnalysisViewModel,
  migratedAnalysisDiagnosticsAsPlatformDiagnostics,
} from "./viewModels/analysisDiagnostics";
import {
  buildLanguageAuditViewModel,
  languageAuditIssuesAsPlatformDiagnostics,
  languageAuditStateForProject,
  type AuditOperationLog,
  type AuditStatus,
  type LanguageAuditViewModel,
} from "./viewModels/languageAudit";
import {
  buildSampleBrowserViewModel,
  sampleBrowserIssuesAsPlatformDiagnostics,
  type ReasonScriptSample,
  type SampleLoadStatus,
  type SampleOperationLog,
} from "./viewModels/sampleBrowser";
import { buildRuntimeObservabilityViewModel } from "./viewModels/runtimeObservability";
import { buildWorkspaceDiagnosticsViewModel, workspaceDiagnosticsAsPlatformDiagnostics } from "./viewModels/workspaceDiagnostics";
import { deriveEditorWorkspaceState } from "./viewModels/editorWorkspaceState";
import { buildArtifactFreshness } from "./viewModels/artifactFreshness";
import { buildProjectValidationSummary } from "./viewModels/projectValidation";
import { mergeProblemsSources } from "./viewModels/problemsOutputLogsIntegration";
import { buildFileDiagnosticsMapping } from "./viewModels/fileDiagnosticsMapping";
import { useProjectStore } from "./state/projectStore";
import { useWorkspaceStore } from "./state/workspaceStore";
import {
  buildProjectState,
  diffArtifactWorkflow,
  exportArtifactWorkflow,
  fetchExamples,
  importArtifactWorkflow,
  exportLanguageAudit,
  runLanguageAudit,
} from "./bridge";
import { revealSourceSpan, revealSymbolFallback } from "./editor/sourceNavigation";
import type { ArtifactSelection, ArtifactKind, FileNode, WorkspaceScanStatus, WorkspaceState } from "./types";
import {
  createCommandRegistry,
  createCommandResult,
  getPlatformAdapter,
  notifyPlatformError,
  setAnalyzeArtifactSource,
  validateNormalizedRelativePath,
} from "./platform";
import type { IdeCommand, WorkspaceFileNode } from "./platform";
import "./App.css";

// v0.6-C: model is the preferred top-level construct for new code
const DEFAULT_SOURCE = `// ReasonScript IDE
model HelloWorld {
  calculation Answer {
    result = 42
  }
}
`;

interface ArtifactWorkflowClientState {
  fileKey?: string;
  exportResult?: unknown;
  importResult?: unknown;
  diffResult?: unknown;
  logs: ArtifactOperationLog[];
  lastOperation?: ArtifactOperationKind;
  lastStatus?: ArtifactOperationStatus;
}

type ArtifactDiffSlots = {
  a?: unknown;
  b?: unknown;
};

const EMPTY_ARTIFACT_WORKFLOW_STATE: ArtifactWorkflowClientState = {
  logs: [],
};

interface LanguageAuditClientState {
  fileKey?: string;
  sourceSnapshot?: string;
  auditResult?: unknown;
  exportResult?: unknown;
  logs: AuditOperationLog[];
  lastRunAt?: string;
}

const EMPTY_LANGUAGE_AUDIT_STATE: LanguageAuditClientState = {
  logs: [],
};

interface SampleBrowserClientState {
  status?: "idle" | "loading" | "loaded" | "failed" | "unavailable";
  examples?: unknown;
  selectedSampleId?: string;
  issues: unknown[];
  logs: SampleOperationLog[];
}

const EMPTY_SAMPLE_BROWSER_STATE: SampleBrowserClientState = {
  status: "idle",
  issues: [],
  logs: [],
};

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
  const [compilerMode, setCompilerMode] = useState("normal");
  const [activeInspectorTab, setActiveInspectorTab] = useState("overview");
  const [activeBottomTab, setActiveBottomTab] = useState("problems");
  const [artifactWorkflowState, setArtifactWorkflowState] = useState<ArtifactWorkflowClientState>(EMPTY_ARTIFACT_WORKFLOW_STATE);
  const [artifactDiffSlots, setArtifactDiffSlots] = useState<ArtifactDiffSlots>({});
  const [artifactOperationRunning, setArtifactOperationRunning] = useState(false);
  const [languageAuditState, setLanguageAuditState] = useState<LanguageAuditClientState>(EMPTY_LANGUAGE_AUDIT_STATE);
  const [auditOperationRunning, setAuditOperationRunning] = useState(false);
  const [sampleBrowserState, setSampleBrowserState] = useState<SampleBrowserClientState>(EMPTY_SAMPLE_BROWSER_STATE);
  const [sampleOperationRunning, setSampleOperationRunning] = useState(false);
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);
  const store = useProjectStore();
  const wsStore = useWorkspaceStore();
  const platform = useMemo(() => getPlatformAdapter(), []);
  const commandRegistry = useMemo(() => createCommandRegistry(), []);
  const currentArtifactFileKey = wsStore.selectedPath ?? store.projectState?.metadata?.source_filename ?? "temporary source";
  const currentAuditFileKey = wsStore.selectedPath ?? wsStore.workspace?.root_path ?? store.projectState?.metadata?.source_filename ?? "temporary source";
  const editorDirty = source !== savedSource;

  const appendArtifactLog = useCallback((
    operation: ArtifactOperationKind,
    status: ArtifactOperationStatus,
    message: string,
    evidence?: unknown
  ) => {
    const timestamp = new Date().toISOString();
    setArtifactWorkflowState((previous) => ({
      ...previous,
      fileKey: currentArtifactFileKey,
      lastOperation: operation,
      lastStatus: status,
      logs: [
        ...previous.logs,
        {
          id: `${operation}-${timestamp}-${previous.logs.length}`,
          operation,
          status,
          message,
          timestamp,
          evidence,
        },
      ],
    }));
  }, [currentArtifactFileKey]);

  const recordArtifactResult = useCallback((
    operation: ArtifactOperationKind,
    status: ArtifactOperationStatus,
    result: unknown
  ) => {
    setArtifactWorkflowState((previous) => ({
      ...previous,
      fileKey: currentArtifactFileKey,
      exportResult: operation === "export" ? result : previous.exportResult,
      importResult: operation === "import" ? result : previous.importResult,
      diffResult: operation === "diff" ? result : previous.diffResult,
      lastOperation: operation,
      lastStatus: status,
    }));
  }, [currentArtifactFileKey]);

  const appendLanguageAuditLog = useCallback((
    status: AuditStatus,
    message: string,
    evidence?: unknown
  ) => {
    const timestamp = new Date().toISOString();
    setLanguageAuditState((previous) => ({
      ...previous,
      fileKey: currentAuditFileKey,
      logs: [
        ...previous.logs,
        {
          id: `language-audit-${timestamp}-${previous.logs.length}`,
          status,
          message,
          timestamp,
          evidence,
        },
      ],
    }));
  }, [currentAuditFileKey]);

  const recordLanguageAuditResult = useCallback((auditResult: unknown) => {
    setLanguageAuditState((previous) => ({
      ...previous,
      fileKey: currentAuditFileKey,
      sourceSnapshot: source,
      auditResult,
      lastRunAt: new Date().toISOString(),
    }));
  }, [currentAuditFileKey, source]);

  const recordLanguageAuditExportResult = useCallback((exportResult: unknown) => {
    setLanguageAuditState((previous) => ({
      ...previous,
      fileKey: currentAuditFileKey,
      exportResult,
      auditResult: (exportResult && typeof exportResult === "object" && "matrix" in exportResult)
        ? exportResult
        : previous.auditResult,
      lastRunAt: previous.lastRunAt ?? new Date().toISOString(),
    }));
  }, [currentAuditFileKey]);

  const appendSampleLog = useCallback((
    status: SampleLoadStatus,
    message: string,
    sampleId?: string,
    evidence?: unknown
  ) => {
    const timestamp = new Date().toISOString();
    setSampleBrowserState((previous) => ({
      ...previous,
      logs: [
        ...previous.logs,
        {
          id: `sample-${timestamp}-${previous.logs.length}`,
          status,
          message,
          sampleId,
          timestamp,
          evidence,
        },
      ],
    }));
  }, []);

  const appendSampleIssue = useCallback((message: string, sampleId?: string, code = "SAMPLE_LOAD_FAILED", evidence?: unknown) => {
    setSampleBrowserState((previous) => ({
      ...previous,
      issues: [
        ...previous.issues,
        {
          id: `sample-issue-${new Date().toISOString()}-${previous.issues.length}`,
          severity: "error",
          code,
          message,
          sampleId,
          evidence,
        },
      ],
    }));
  }, []);

  useEffect(() => {
    platform.commands = commandRegistry;
  }, [commandRegistry, platform]);

  useEffect(() => {
    setArtifactWorkflowState((previous) => {
      if (!previous.fileKey || previous.fileKey === currentArtifactFileKey) return previous;
      return EMPTY_ARTIFACT_WORKFLOW_STATE;
    });
    setArtifactDiffSlots({});
  }, [currentArtifactFileKey]);

  useEffect(() => {
    setLanguageAuditState((previous) => {
      if (!previous.fileKey || previous.fileKey === currentAuditFileKey) return previous;
      return EMPTY_LANGUAGE_AUDIT_STATE;
    });
  }, [currentAuditFileKey]);

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

  useEffect(() => {
    let cancelled = false;

    async function restoreSettings() {
      const [storedMode, storedInspectorTab, storedBottomTab] = await Promise.all([
        platform.settings.get<string>("compilerMode"),
        platform.settings.get<string>("rightInspector.activeTab"),
        platform.settings.get<string>("bottomToolWindow.activeTab"),
      ]);

      if (cancelled) return;
      if (storedMode) setCompilerMode(storedMode);
      if (storedInspectorTab) setActiveInspectorTab(storedInspectorTab);
      if (storedBottomTab) setActiveBottomTab(storedBottomTab);
    }

    restoreSettings().catch((cause) => {
      platform.notifications.warning("Settings could not be restored.", {
        operation: "settings.restore",
        details: cause instanceof Error ? cause.message : String(cause),
      });
    });

    return () => {
      cancelled = true;
    };
  }, [platform]);

  const setInspectorTab = useCallback((tabId: string) => {
    setActiveInspectorTab(tabId);
    platform.settings.set("rightInspector.activeTab", tabId).catch((cause) => {
      platform.notifications.warning("Right inspector tab setting could not be saved.", {
        operation: "settings.set",
        details: cause instanceof Error ? cause.message : String(cause),
      });
    });
  }, [platform]);

  const setBottomToolTab = useCallback((tabId: string) => {
    setActiveBottomTab(tabId);
    platform.settings.set("bottomToolWindow.activeTab", tabId).catch((cause) => {
      platform.notifications.warning("Bottom tool tab setting could not be saved.", {
        operation: "settings.set",
        details: cause instanceof Error ? cause.message : String(cause),
      });
    });
  }, [platform]);

  const refreshSamples = useCallback(async () => {
    setSampleOperationRunning(true);
    setSampleBrowserState((previous) => ({ ...previous, status: "loading" }));
    appendSampleLog("loading", "Examples fetch started.");
    try {
      const examples = await fetchExamples();
      setSampleBrowserState((previous) => ({
        ...previous,
        status: "loaded",
        examples,
      }));
      const count = Array.isArray(examples)
        ? examples.length
        : Array.isArray((examples as Record<string, unknown> | null)?.examples)
          ? ((examples as Record<string, unknown>).examples as unknown[]).length
          : 0;
      appendSampleLog("loaded", `Examples fetch completed: ${count} samples.`, undefined, examples);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setSampleBrowserState((previous) => ({ ...previous, status: "failed" }));
      appendSampleIssue(`Example loading failed: ${message}`, undefined, "SAMPLE_FETCH_FAILED", error);
      appendSampleLog("failed", `Examples fetch failed: ${message}`, undefined, error);
      platform.notifications.error("Examples unavailable.", { operation: "examples.fetch", details: message });
      setBottomToolTab("problems");
    } finally {
      setSampleOperationRunning(false);
    }
  }, [appendSampleIssue, appendSampleLog, platform.notifications, setBottomToolTab]);

  useEffect(() => {
    refreshSamples();
  }, [refreshSamples]);

  const handleSelectSample = useCallback((sampleId: string) => {
    setSampleBrowserState((previous) => ({ ...previous, selectedSampleId: sampleId }));
  }, []);

  const handleLoadSample = useCallback((sample: ReasonScriptSample) => {
    setSampleBrowserState((previous) => ({ ...previous, selectedSampleId: sample.id }));
    if (!sample.source) {
      appendSampleIssue("Sample source unavailable.", sample.id, "SAMPLE_SOURCE_UNAVAILABLE", sample.raw);
      appendSampleLog("failed", "Sample source unavailable.", sample.id, sample.raw);
      setBottomToolTab("problems");
      return;
    }
    if (editorDirty) {
      appendSampleIssue("Unsaved editor content blocks example loading.", sample.id, "SAMPLE_LOAD_BLOCKED", sample.raw);
      appendSampleLog("blocked", "Sample load blocked because the editor has unsaved content.", sample.id, sample.raw);
      setBottomToolTab("problems");
      return;
    }

    setSource(sample.source);
    setSavedSource(sample.source);
    setSelectedVersion(undefined);
    setSelectedReadOnly(false);
    wsStore.setSelectedPath(null);
    wsStore.setActiveFilePath(null);
    store.setLastError(null);
    appendSampleLog("loaded", `Example loaded: ${sample.title}`, sample.id, sample.raw);
    setBottomToolTab("output");
  }, [
    appendSampleIssue,
    appendSampleLog,
    editorDirty,
    setBottomToolTab,
    store,
    wsStore,
  ]);

  const setCompilerModeSetting = useCallback((mode: string) => {
    setCompilerMode(mode);
    platform.settings.set("compilerMode", mode).catch((cause) => {
      platform.notifications.warning("Compiler mode setting could not be saved.", {
        operation: "settings.set",
        details: cause instanceof Error ? cause.message : String(cause),
      });
    });
  }, [platform]);

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
          notifyPlatformError(platform.notifications, pathResult.error);
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
        compilerMode,
        sourceContext
      );
      store.setProjectState(state);
      setAnalyzeArtifactSource(state);
    } catch (e) {
      const message = e instanceof Error ? (e.stack ?? e.message) : String(e);
      store.setBuildStatus("error");
      store.setLastError(message);
      platform.notifications.error("Analyze failed.", {
        operation: "analyzeFile",
        details: message,
      });
    }
  }, [compilerMode, platform.notifications, savedSource, source, store, wsStore.selectedPath, wsStore.workspace]);

  const handleOpenWorkspace = useCallback(async (rootPath: string) => {
    const result = await platform.workspace.listWorkspace({ workspaceRoot: rootPath });
    if (!result.ok) {
      notifyPlatformError(platform.notifications, result.error);
      throw new Error(result.error.message);
    }
    wsStore.setWorkspace(workspaceFromAdapterResult(result.root, result.files, result.scanStatus));
    wsStore.setSelectedPath(null);
    wsStore.setActiveFilePath(null);
  }, [platform, wsStore]);

  const handleRefreshWorkspace = useCallback(async () => {
    if (!wsStore.workspace) return;
    const result = await platform.workspace.listWorkspace({ workspaceRoot: wsStore.workspace.root_path });
    if (!result.ok) {
      notifyPlatformError(platform.notifications, result.error);
      throw new Error(result.error.message);
    }
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
      notifyPlatformError(platform.notifications, pathResult.error);
      return;
    }

    const result = await platform.workspace.readFile({
      workspaceRoot: wsStore.workspace.root_path,
      relativePath: pathResult.relativePath,
    });
    if (!result.ok) {
      store.setLastError(result.error.message);
      notifyPlatformError(platform.notifications, result.error);
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
      platform.notifications.warning("Selected file is read-only.", { operation: "saveFile" });
      return;
    }
    const pathResult = validateNormalizedRelativePath(wsStore.selectedPath);
    if (!pathResult.ok) {
      store.setLastError(pathResult.error.message);
      notifyPlatformError(platform.notifications, pathResult.error);
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
      notifyPlatformError(platform.notifications, result.error);
      return;
    }
    setSelectedVersion(result.version);
    setSavedSource(source);
    store.setLastError(null);
    platform.notifications.info("File saved.", {
      operation: "saveFile",
      details: pathResult.relativePath,
    });
  }, [platform, selectedReadOnly, selectedVersion, source, store, wsStore.selectedPath, wsStore.workspace]);

  const handleRunLanguageAudit = useCallback(async () => {
    setAuditOperationRunning(true);
    appendLanguageAuditLog("warning", "Audit started.");
    try {
      const result = await runLanguageAudit();
      recordLanguageAuditResult(result);
      const record = result && typeof result === "object" ? result as Record<string, unknown> : {};
      const matrix = record.matrix && typeof record.matrix === "object" ? record.matrix as Record<string, unknown> : {};
      const summary = matrix.summary && typeof matrix.summary === "object" ? matrix.summary as Record<string, unknown> : {};
      appendLanguageAuditLog(
        record.ok === false ? "fail" : "pass",
        `Audit completed: connected ${String(summary.connected ?? 0)}/${String(summary.total ?? 0)}.`,
        result
      );
      setBottomToolTab("tests");
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      const failure = { ok: false, errors: [{ severity: "error", message, phase: "LanguageAudit" }] };
      recordLanguageAuditResult(failure);
      appendLanguageAuditLog("fail", `Audit failed: ${message}`, failure);
      platform.notifications.error("Language audit failed.", { operation: "languageAudit.run", details: message });
      setBottomToolTab("problems");
    } finally {
      setAuditOperationRunning(false);
    }
  }, [
    appendLanguageAuditLog,
    platform.notifications,
    recordLanguageAuditResult,
    setBottomToolTab,
  ]);

  const handleExportLanguageAudit = useCallback(async () => {
    setAuditOperationRunning(true);
    appendLanguageAuditLog("warning", "Audit export started.");
    try {
      const result = await exportLanguageAudit();
      recordLanguageAuditExportResult(result);
      const record = result && typeof result === "object" ? result as Record<string, unknown> : {};
      const files = record.files && typeof record.files === "object" ? record.files as Record<string, unknown> : {};
      appendLanguageAuditLog(
        record.ok === false ? "fail" : "pass",
        `Audit export completed${files.audit ? `: ${String(files.audit)}` : "."}`,
        result
      );
      setInspectorTab("artifacts");
      setBottomToolTab("output");
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      const failure = { ok: false, errors: [{ severity: "error", message, phase: "LanguageAuditExport" }] };
      recordLanguageAuditExportResult(failure);
      appendLanguageAuditLog("fail", `Audit export failed: ${message}`, failure);
      platform.notifications.error("Language audit export failed.", { operation: "languageAudit.export", details: message });
      setBottomToolTab("problems");
    } finally {
      setAuditOperationRunning(false);
    }
  }, [
    appendLanguageAuditLog,
    platform.notifications,
    recordLanguageAuditExportResult,
    setBottomToolTab,
    setInspectorTab,
  ]);

  useEffect(() => {
    commandRegistry.register("saveFile", async (request) => {
      await saveCurrentFile();
      return createCommandResult(request, "Save complete.");
    });
    commandRegistry.register("analyzeFile", async (request) => {
      await runBuild();
      return createCommandResult(request, "Analyze complete.");
    });
    commandRegistry.register("runCurrentFile", async (request) => {
      await runBuild();
      return createCommandResult(request, "Run complete.");
    });
    commandRegistry.register("validateWorkspace", async (request) => {
      await runBuild();
      return createCommandResult(request, "Validate complete.");
    });
    commandRegistry.register("auditProject", async (request) => {
      await handleRunLanguageAudit();
      return createCommandResult(request, "Audit complete.");
    });
    commandRegistry.register("showOverview", async (request) => {
      setInspectorTab("overview");
      return createCommandResult(request);
    });
    commandRegistry.register("showPlan", async (request) => {
      setInspectorTab("plan");
      return createCommandResult(request);
    });
    commandRegistry.register("showSimulation", async (request) => {
      setInspectorTab("simulation");
      return createCommandResult(request);
    });
    commandRegistry.register("showKnowledge", async (request) => {
      setInspectorTab("knowledge");
      return createCommandResult(request);
    });
    commandRegistry.register("showArtifacts", async (request) => {
      setInspectorTab("artifacts");
      return createCommandResult(request);
    });
    commandRegistry.register("showProblems", async (request) => {
      setBottomToolTab("problems");
      return createCommandResult(request);
    });
    commandRegistry.register("showOutput", async (request) => {
      setBottomToolTab("output");
      return createCommandResult(request);
    });
    commandRegistry.register("showLogs", async (request) => {
      setBottomToolTab("logs");
      return createCommandResult(request);
    });
    commandRegistry.register("showTests", async (request) => {
      setBottomToolTab("tests");
      return createCommandResult(request);
    });
    commandRegistry.register("clearOutput", async (request) => {
      store.setLastError(null);
      return createCommandResult(request, "Output cleared.");
    });
    commandRegistry.register("clearNotifications", async (request) => createCommandResult(request));
  }, [
    commandRegistry,
    handleRunLanguageAudit,
    runBuild,
    saveCurrentFile,
    setBottomToolTab,
    setInspectorTab,
    store,
  ]);

  const executeCommand = useCallback(
    async (command: IdeCommand, source: "top_bar" | "shortcut" | "menu" | "panel" | "system" = "panel") => {
      const result = await commandRegistry.execute({ command, source });
      if (!result.ok && result.error) {
        notifyPlatformError(platform.notifications, result.error);
      }
      return result;
    },
    [commandRegistry, platform.notifications]
  );

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const meta = e.metaKey || e.ctrlKey;
      if (meta && e.key === "b") { e.preventDefault(); executeCommand("analyzeFile", "shortcut"); }
      else if (meta && e.key === "Enter") { e.preventDefault(); executeCommand("analyzeFile", "shortcut"); }
      else if (meta && e.key.toLowerCase() === "s") { e.preventDefault(); executeCommand("saveFile", "shortcut"); }
      else if (meta && e.shiftKey && e.key.toLowerCase() === "m") { e.preventDefault(); executeCommand("showProblems", "shortcut"); }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [executeCommand]);

  const currentArtifactsForDiff = useCallback(() => {
    if (!store.projectState) return null;
    return store.projectState?.artifacts ?? {
      surface_ast: store.projectState?.surface_ast,
      semantic_ast: store.projectState?.semantic_ast,
      reason_ir: store.projectState?.reason_ir,
      execution_plan: store.projectState?.execution_plan,
      simulation: store.projectState?.simulation,
      knowledge: store.projectState?.knowledge,
      validation: store.projectState?.validation,
    };
  }, [store.projectState]);

  const handleExport = useCallback(async () => {
    setArtifactOperationRunning(true);
    appendArtifactLog("export", "running", "Export started.");
    try {
      const result = await exportArtifactWorkflow(source, wsStore.selectedPath ?? "playground.rsn");
      recordArtifactResult("export", "success", result);
      const record = result && typeof result === "object" ? result as Record<string, unknown> : {};
      appendArtifactLog("export", "success", `Export completed${record.path ? `: ${String(record.path)}` : "."}`, result);
      setInspectorTab("artifacts");
      setBottomToolTab("output");
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      const failure: ExportArtifactResult = {
        status: "failed",
        raw: { ok: false, errors: [{ severity: "error", message, phase: "Export" }] },
      };
      recordArtifactResult("export", "failed", failure);
      appendArtifactLog("export", "failed", `Export failed: ${message}`, failure.raw);
      platform.notifications.error("Export failed.", { operation: "artifact.export", details: message });
    } finally {
      setArtifactOperationRunning(false);
    }
  }, [
    appendArtifactLog,
    platform.notifications,
    recordArtifactResult,
    setBottomToolTab,
    setInspectorTab,
    source,
    wsStore.selectedPath,
  ]);

  const handleImportArtifact = useCallback(async (path: string) => {
    const trimmed = path.trim();
    if (!trimmed) return;
    setArtifactOperationRunning(true);
    appendArtifactLog("import", "running", `Import started: ${trimmed}`);
    try {
      const result = await importArtifactWorkflow(trimmed);
      recordArtifactResult("import", "success", result);
      const record = result && typeof result === "object" ? result as Record<string, unknown> : {};
      if (record.artifacts) setArtifactDiffSlots((previous) => ({ ...previous, b: record.artifacts }));
      appendArtifactLog("import", "success", `Import completed${record.path ? `: ${String(record.path)}` : "."}`, result);
      setInspectorTab("artifacts");
      setBottomToolTab("output");
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      const failure: ImportArtifactResult = {
        status: "failed",
        validationIssues: [{ id: "import-failure", operation: "import", severity: "error", code: "IMPORT_FAILED", message }],
        raw: { ok: false, errors: [{ severity: "error", message, phase: "Import", path: trimmed }] },
      };
      recordArtifactResult("import", "failed", failure);
      appendArtifactLog("import", "failed", `Import failed: ${message}`, failure.raw);
      platform.notifications.error("Import failed.", { operation: "artifact.import", details: message });
      setBottomToolTab("problems");
    } finally {
      setArtifactOperationRunning(false);
    }
  }, [appendArtifactLog, platform.notifications, recordArtifactResult, setBottomToolTab, setInspectorTab]);

  const handleSetArtifactDiffSlot = useCallback((slot: "a" | "b") => {
    const artifacts = currentArtifactsForDiff();
    if (!artifacts) {
      appendArtifactLog("diff", "failed", "Diff slot could not be set because no current artifacts are available.");
      return;
    }
    setArtifactDiffSlots((previous) => ({ ...previous, [slot]: artifacts }));
    appendArtifactLog("diff", "success", `Diff slot ${slot.toUpperCase()} set.`);
  }, [appendArtifactLog, currentArtifactsForDiff]);

  const handleCompareArtifactDiff = useCallback(async () => {
    if (!artifactDiffSlots.a || !artifactDiffSlots.b) return;
    setArtifactOperationRunning(true);
    appendArtifactLog("diff", "running", "Diff started.");
    try {
      const result = await diffArtifactWorkflow(artifactDiffSlots.a, artifactDiffSlots.b);
      recordArtifactResult("diff", "success", result);
      const record = result && typeof result === "object" ? result as Record<string, unknown> : {};
      const summary = record.summary && typeof record.summary === "object" ? record.summary as Record<string, unknown> : {};
      appendArtifactLog("diff", "success", `Diff completed: changed ${String(summary.changed ?? 0)}.`, result);
      setInspectorTab("artifacts");
      setBottomToolTab("output");
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      const failure: DiffArtifactResult = {
        status: "failed",
        issues: [{ id: "diff-failure", operation: "diff", severity: "error", code: "DIFF_FAILED", message }],
        raw: { ok: false, errors: [{ severity: "error", message, phase: "Diff" }] },
      };
      recordArtifactResult("diff", "failed", failure);
      appendArtifactLog("diff", "failed", `Diff failed: ${message}`, failure.raw);
      platform.notifications.error("Diff failed.", { operation: "artifact.diff", details: message });
      setBottomToolTab("problems");
    } finally {
      setArtifactOperationRunning(false);
    }
  }, [
    appendArtifactLog,
    artifactDiffSlots.a,
    artifactDiffSlots.b,
    platform.notifications,
    recordArtifactResult,
    setBottomToolTab,
    setInspectorTab,
  ]);

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
    if (target) setInspectorTab(target);
  }, [setInspectorTab]);

  const ps = store.projectState;
  const psWithArtifactWorkflow = useMemo(
    () => artifactWorkflowStateForProject(ps, artifactWorkflowState),
    [artifactWorkflowState, ps]
  );
  const languageAuditStateWithFreshness = useMemo(
    () => ({
      ...languageAuditState,
      stale: Boolean(languageAuditState.sourceSnapshot && languageAuditState.sourceSnapshot !== source),
    }),
    [languageAuditState, source]
  );
  const psWithLanguageAudit = useMemo(
    () => languageAuditStateForProject(ps, languageAuditStateWithFreshness),
    [languageAuditStateWithFreshness, ps]
  );
  const sel = store.selectedArtifact;

  // Build view models (memoized)
  const pipelineVm = useMemo(() => buildPipelineOverview(ps), [ps]);
  const sourceModelVm = useMemo(() => buildSourceModel(ps?.surface_ast), [ps?.surface_ast]);
  const executionPlanVm = useMemo(() => buildExecutionPlanFlow(ps?.execution_plan), [ps?.execution_plan]);
  const simulationVm = useMemo(() => buildSimulationTrace(ps?.simulation), [ps?.simulation]);
  const knowledgeVm = useMemo(() => buildKnowledgeEvidence(ps?.knowledge), [ps?.knowledge]);
  const diagnosticsAnalysisVm = useMemo(() => buildDiagnosticsAnalysisViewModel(ps), [ps]);
  const runtimeObservabilityVm = useMemo(() => buildRuntimeObservabilityViewModel(ps), [ps]);
  const artifactWorkflowVm: ArtifactWorkflowViewModel = useMemo(
    () => buildArtifactWorkflowViewModel(psWithArtifactWorkflow ?? { artifactWorkflow: artifactWorkflowState }),
    [artifactWorkflowState, psWithArtifactWorkflow]
  );
  const languageAuditVm: LanguageAuditViewModel = useMemo(
    () => buildLanguageAuditViewModel(psWithLanguageAudit ?? { languageAudit: languageAuditStateWithFreshness }),
    [languageAuditStateWithFreshness, psWithLanguageAudit]
  );
  const sampleBrowserVm = useMemo(
    () => buildSampleBrowserViewModel({
      status: sampleBrowserState.status,
      examples: sampleBrowserState.examples,
      selectedSampleId: sampleBrowserState.selectedSampleId,
      issues: sampleBrowserState.issues,
      logs: sampleBrowserState.logs,
    }),
    [sampleBrowserState]
  );
  const migratedDiagnostics = useMemo(
    () => migratedAnalysisDiagnosticsAsPlatformDiagnostics(diagnosticsAnalysisVm),
    [diagnosticsAnalysisVm]
  );
  const artifactWorkflowDiagnostics = useMemo(
    () => artifactWorkflowIssuesAsPlatformDiagnostics(artifactWorkflowVm),
    [artifactWorkflowVm]
  );
  const languageAuditDiagnostics = useMemo(
    () => languageAuditIssuesAsPlatformDiagnostics(languageAuditVm),
    [languageAuditVm]
  );
  const sampleBrowserDiagnostics = useMemo(
    () => sampleBrowserIssuesAsPlatformDiagnostics(sampleBrowserVm),
    [sampleBrowserVm]
  );
  const workspaceDiagnosticsVm = useMemo(
    () => buildWorkspaceDiagnosticsViewModel(wsStore.workspace),
    [wsStore.workspace]
  );
  const workspaceDiagnosticsList = useMemo(
    () => workspaceDiagnosticsAsPlatformDiagnostics(workspaceDiagnosticsVm),
    [workspaceDiagnosticsVm]
  );
  const editorWorkspaceState = useMemo(
    () => deriveEditorWorkspaceState({
      selectedPath: wsStore.selectedPath,
      activeFilePath: wsStore.activeFilePath,
      sampleId: sampleBrowserState.selectedSampleId,
      source,
      savedSource,
      workspace: wsStore.workspace,
    }),
    [sampleBrowserState.selectedSampleId, savedSource, source, wsStore.activeFilePath, wsStore.selectedPath, wsStore.workspace]
  );
  const artifactFreshnessVm = useMemo(
    () => buildArtifactFreshness(ps, source),
    [ps, source]
  );
  const problemsDiagnostics = useMemo(
    () => mergeProblemsSources([
      migratedDiagnostics,
      artifactWorkflowDiagnostics,
      languageAuditDiagnostics,
      sampleBrowserDiagnostics,
      workspaceDiagnosticsList,
    ]),
    [artifactWorkflowDiagnostics, languageAuditDiagnostics, migratedDiagnostics, sampleBrowserDiagnostics, workspaceDiagnosticsList]
  );
  const projectValidationSummary = useMemo(
    () => buildProjectValidationSummary(wsStore.workspace, workspaceDiagnosticsVm, problemsDiagnostics, artifactFreshnessVm),
    [artifactFreshnessVm, problemsDiagnostics, workspaceDiagnosticsVm, wsStore.workspace]
  );
  const fileDiagnosticsMappingForExplorer = useMemo(
    () => buildFileDiagnosticsMapping(problemsDiagnostics, wsStore.selectedPath),
    [problemsDiagnostics, wsStore.selectedPath]
  );

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
          diagnosticsAnalysisVm={diagnosticsAnalysisVm}
          artifactWorkflowVm={artifactWorkflowVm}
          languageAuditVm={languageAuditVm}
          runtimeObservabilityVm={runtimeObservabilityVm}
          workspaceDiagnosticsVm={workspaceDiagnosticsVm}
          artifactFreshnessVm={artifactFreshnessVm}
          projectValidationSummary={projectValidationSummary}
          onRunLanguageAudit={handleRunLanguageAudit}
          onExportLanguageAudit={handleExportLanguageAudit}
          auditOperationRunning={auditOperationRunning}
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
          runtimeObservabilityVm={runtimeObservabilityVm}
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
          artifactWorkflowVm={artifactWorkflowVm}
          languageAuditVm={languageAuditVm}
          sampleBrowserVm={sampleBrowserVm}
          artifactDiffSlotAReady={Boolean(artifactDiffSlots.a)}
          artifactDiffSlotBReady={Boolean(artifactDiffSlots.b)}
          onExportArtifact={handleExport}
          onImportArtifact={handleImportArtifact}
          onSetArtifactDiffSlot={handleSetArtifactDiffSlot}
          onCompareArtifactDiff={handleCompareArtifactDiff}
          artifactOperationRunning={artifactOperationRunning}
          selectedArtifact={sel}
          onSelectArtifact={handleSelectArtifact}
          projectValidationSummary={projectValidationSummary}
          artifactFreshnessVm={artifactFreshnessVm}
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
        onSave={() => executeCommand("saveFile", "top_bar")}
        onRun={() => executeCommand("runCurrentFile", "top_bar")}
        onAnalyze={() => executeCommand("analyzeFile", "top_bar")}
        onValidate={() => executeCommand("validateWorkspace", "top_bar")}
        onAudit={() => executeCommand("auditProject", "top_bar")}
        onExport={handleExport}
        onCompilerModeChange={setCompilerModeSetting}
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
          sampleBrowserVm={sampleBrowserVm}
          selectedSampleId={sampleBrowserState.selectedSampleId}
          sampleLoading={sampleOperationRunning}
          editorDirty={editorDirty}
          diagnosticsMapping={fileDiagnosticsMappingForExplorer}
          editorWorkspaceState={editorWorkspaceState}
          ignoredPathCount={workspaceDiagnosticsVm.ignoredPaths.length}
          onSelectPath={handleSelectWorkspacePath}
          onToggleExpanded={wsStore.toggleExpanded}
          onClearWorkspace={wsStore.clearWorkspace}
          onOpenWorkspace={handleOpenWorkspace}
          onRefreshWorkspace={handleRefreshWorkspace}
          onRefreshSamples={refreshSamples}
          onSelectSample={handleSelectSample}
          onLoadSample={handleLoadSample}
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
            diagnostics={problemsDiagnostics}
            diagnosticsAnalysisVm={diagnosticsAnalysisVm}
            artifactWorkflowVm={artifactWorkflowVm}
            languageAuditVm={languageAuditVm}
            sampleBrowserVm={sampleBrowserVm}
            runtimeObservabilityVm={runtimeObservabilityVm}
            simulationVm={simulationVm}
            workspaceDiagnosticsVm={workspaceDiagnosticsVm}
            activeRelativePath={wsStore.selectedPath}
            projectState={ps}
            lastError={store.lastError}
            selectedArtifact={sel}
            onSelectArtifact={handleSelectArtifact}
            activeTab={activeBottomTab}
            onActiveTabChange={setBottomToolTab}
            onRunLanguageAudit={handleRunLanguageAudit}
            onExportLanguageAudit={handleExportLanguageAudit}
            auditOperationRunning={auditOperationRunning}
          />
        </div>

        <div className="ide-right-pane">
          <TabPanel
            tabs={rightInspectorTabs}
            activeTab={activeInspectorTab}
            onActiveTabChange={setInspectorTab}
          />
        </div>
      </div>

      {store.lastError && (
        <div className="ide-error-bar">{store.lastError}</div>
      )}
    </div>
  );
}
