import { useEffect, useState } from "react";
import TabPanel from "../components/TabPanel";
import type { DiagnosticsAnalysisViewModel } from "../viewModels/analysisDiagnostics";
import type { ArtifactWorkflowViewModel } from "../viewModels/artifactWorkflow";
import type { LanguageAuditViewModel } from "../viewModels/languageAudit";
import type { RuntimeObservabilityViewModel } from "../viewModels/runtimeObservability";
import type { SampleBrowserViewModel } from "../viewModels/sampleBrowser";
import type { WorkspaceDiagnosticsViewModel } from "../viewModels/workspaceDiagnostics";
import type { ArtifactFreshnessViewModel } from "../viewModels/artifactFreshness";
import type { ProjectValidationSummary } from "../viewModels/projectValidation";
import type { ReasoningRuntimeViewModel } from "../types/reasoningOverview";
import {
  buildFileDiagnosticsMapping,
  filterByScope,
  type DiagnosticScope,
} from "../viewModels/fileDiagnosticsMapping";
import { buildLogsGroups } from "../viewModels/problemsOutputLogsIntegration";
import type {
  ArtifactSelection,
  PlatformDiagnostic,
  ProjectState,
} from "../types";
import type {
  KnowledgeViewModel,
  PipelineOverviewViewModel,
  SimulationTraceViewModel,
} from "../visualization/viewModels";
import DependencyGraphView from "./DependencyGraphView";
import AnalysisSummaryView from "./AnalysisSummaryView";
import ArtifactOperationLogsView from "./ArtifactOperationLogsView";
import ArtifactWorkflowSummaryView from "./ArtifactWorkflowSummaryView";
import ArtifactWorkflowView from "./ArtifactWorkflowView";
import DiagnosticsView from "./DiagnosticsView";
import DiagnosticsAnalysisView from "./DiagnosticsAnalysisView";
import LanguageAuditArtifactsView from "./LanguageAuditArtifactsView";
import LanguageAuditLogsView from "./LanguageAuditLogsView";
import LanguageAuditMatrixView from "./LanguageAuditMatrixView";
import LanguageAuditSummaryView from "./LanguageAuditSummaryView";
import RuntimeObservabilitySummaryView from "./RuntimeObservabilitySummaryView";
import RuntimeOutputView from "./RuntimeOutputView";
import SampleOperationLogsView from "./SampleOperationLogsView";
import SampleMetadataView from "./SampleMetadataView";
import WorkspaceDiagnosticsSummaryView from "./WorkspaceDiagnosticsSummaryView";
import ProjectValidationSummaryView from "./ProjectValidationSummaryView";
import ArtifactFreshnessSummaryView from "./ArtifactFreshnessSummaryView";
import JsonArtifactView from "./JsonArtifactView";
import ReasoningOverviewView from "./ReasoningOverviewView";
import PipelineOverviewView from "./PipelineOverviewView";
import ReasonIRView from "./ReasonIRView";
import RuntimeOperationsView from "./RuntimeOperationsView";
import SourceModelView from "./SourceModelView";
import ValidationView from "./ValidationView";
import type { SourceModelViewModel } from "../visualization/viewModels";
import { getPlatformAdapter } from "../platform";
import type { ArtifactDescriptor } from "../platform";

interface SelectionProps {
  selectedArtifact?: ArtifactSelection | null;
  onSelectArtifact?: (sel: ArtifactSelection | null) => void;
}

function countBySeverity(diagnostics: PlatformDiagnostic[]) {
  return diagnostics.reduce(
    (acc, diagnostic) => {
      acc[diagnostic.severity] = (acc[diagnostic.severity] ?? 0) + 1;
      return acc;
    },
    {} as Record<string, number>
  );
}

function getArtifactStatus(data: unknown) {
  if (data == null) return "unavailable";
  if (Array.isArray(data) && data.length === 0) return "empty";
  return "available";
}

type ArtifactContentByFile = Record<string, unknown>;

function SummaryMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="ide-summary-metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

interface OverviewProps {
  projectState: ProjectState | null;
  source: string;
  compilerMode: string;
  buildStatus: string;
  pipelineVm: PipelineOverviewViewModel;
  knowledgeVm: KnowledgeViewModel;
  diagnosticsAnalysisVm: DiagnosticsAnalysisViewModel;
  artifactWorkflowVm: ArtifactWorkflowViewModel;
  languageAuditVm: LanguageAuditViewModel;
  runtimeObservabilityVm: RuntimeObservabilityViewModel;
  workspaceDiagnosticsVm: WorkspaceDiagnosticsViewModel;
  artifactFreshnessVm: ArtifactFreshnessViewModel;
  projectValidationSummary: ProjectValidationSummary;
  onRunLanguageAudit: () => void;
  onExportLanguageAudit: () => void;
  auditOperationRunning?: boolean;
  onNavigate?: (stageId: string) => void;
}

export function StandardOverviewView({
  projectState,
  source,
  compilerMode,
  buildStatus,
  pipelineVm,
  knowledgeVm,
  diagnosticsAnalysisVm,
  artifactWorkflowVm,
  languageAuditVm,
  runtimeObservabilityVm,
  workspaceDiagnosticsVm,
  artifactFreshnessVm,
  projectValidationSummary,
  onRunLanguageAudit,
  onExportLanguageAudit,
  auditOperationRunning,
  onNavigate,
}: OverviewProps) {
  const diagnostics = projectState?.diagnostics ?? [];
  const severity = countBySeverity(diagnostics);
  const passedStages = pipelineVm.stages.filter((stage) => stage.status === "success").length;
  const totalStages = pipelineVm.stages.length;
  const sourceFile = projectState?.metadata?.source_filename ?? "temporary source";
  const outputSteps = pipelineVm.metrics.runtimeOperationCount;
  const artifacts = [
    projectState?.surface_ast,
    projectState?.semantic_ast,
    projectState?.reason_ir,
    projectState?.execution_plan,
    projectState?.simulation,
    projectState?.knowledge,
    projectState?.validation,
  ];
  const availableArtifacts = artifacts.filter((artifact) => artifact != null).length;
  const statusText = projectState
    ? diagnostics.some((d) => d.severity === "error")
      ? "Completed with errors"
      : "Success"
    : buildStatus === "building"
      ? "Running"
      : "No analyze result";

  return (
    <div className="ide-overview">
      <section className="ide-result-card">
        <div className="ide-section-title">Analyze Result</div>
        <div className="ide-summary-grid">
          <SummaryMetric label="File" value={sourceFile} />
          <SummaryMetric label="Mode" value={projectState?.metadata?.compiler_mode ?? compilerMode} />
          <SummaryMetric label="Status" value={statusText} />
          <SummaryMetric label="Pipeline" value={`${passedStages}/${totalStages} passed`} />
          <SummaryMetric
            label="Diagnostics"
            value={`${severity.error ?? 0} errors / ${severity.warning ?? 0} warnings`}
          />
          <SummaryMetric label="Knowledge" value={`${knowledgeVm.knowledgeCount} items`} />
          <SummaryMetric label="Output" value={`${outputSteps} runtime ops`} />
          <SummaryMetric label="Artifacts" value={`${availableArtifacts}/${artifacts.length} available`} />
        </div>
        {!projectState && (
          <div className="ide-muted-note">
            Source is editable. Run Analyze to populate the inspection views.
          </div>
        )}
        {projectState && source !== projectState.source_files?.[0]?.text && (
          <div className="ide-warning-note">Source has changed since the latest analyze result.</div>
        )}
      </section>

      <AnalysisSummaryView vm={diagnosticsAnalysisVm} />
      <RuntimeObservabilitySummaryView vm={runtimeObservabilityVm} />
      <ArtifactWorkflowSummaryView vm={artifactWorkflowVm} />
      <LanguageAuditSummaryView
        vm={languageAuditVm}
        onRunAudit={onRunLanguageAudit}
        onExportAudit={onExportLanguageAudit}
        disabled={auditOperationRunning}
      />
      <WorkspaceDiagnosticsSummaryView vm={workspaceDiagnosticsVm} />
      <ProjectValidationSummaryView summary={projectValidationSummary} />
      <ArtifactFreshnessSummaryView vm={artifactFreshnessVm} />

      <section className="ide-overview-section">
        <div className="ide-section-title">Pipeline</div>
        <PipelineOverviewView
          vm={pipelineVm}
          onNavigate={(_, stageId) => onNavigate?.(stageId)}
        />
      </section>
    </div>
  );
}

interface ArtifactsProps extends SelectionProps {
  projectState: ProjectState | null;
  sourceModelVm: SourceModelViewModel;
  artifactWorkflowVm: ArtifactWorkflowViewModel;
  languageAuditVm: LanguageAuditViewModel;
  sampleBrowserVm: SampleBrowserViewModel;
  artifactDiffSlotAReady: boolean;
  artifactDiffSlotBReady: boolean;
  onExportArtifact: () => void;
  onImportArtifact: (path: string) => void;
  onSetArtifactDiffSlot: (slot: "a" | "b") => void;
  onCompareArtifactDiff: () => void;
  artifactOperationRunning?: boolean;
  projectValidationSummary: ProjectValidationSummary;
  artifactFreshnessVm: ArtifactFreshnessViewModel;
  reasoningOverviewVm: ReasoningRuntimeViewModel;
}

export function ArtifactsInspectorView({
  projectState,
  sourceModelVm,
  artifactWorkflowVm,
  languageAuditVm,
  sampleBrowserVm,
  artifactDiffSlotAReady,
  artifactDiffSlotBReady,
  onExportArtifact,
  onImportArtifact,
  onSetArtifactDiffSlot,
  onCompareArtifactDiff,
  artifactOperationRunning,
  selectedArtifact,
  onSelectArtifact,
  projectValidationSummary,
  artifactFreshnessVm,
  reasoningOverviewVm,
}: ArtifactsProps) {
  const [artifactDescriptors, setArtifactDescriptors] = useState<ArtifactDescriptor[]>([]);
  const [artifactContent, setArtifactContent] = useState<ArtifactContentByFile>({});

  useEffect(() => {
    let cancelled = false;
    async function loadArtifacts() {
      const adapter = getPlatformAdapter().artifacts;
      const index = await adapter.getArtifactIndex({});
      if (!index.ok) {
        if (!cancelled) {
          setArtifactDescriptors([]);
          setArtifactContent({});
        }
        return;
      }

      const entries = await Promise.all(
        index.artifacts.map(async (descriptor) => {
          const result = await adapter.readArtifact({ fileName: descriptor.fileName });
          return [descriptor.fileName, result.ok ? result.content : null] as const;
        })
      );

      if (!cancelled) {
        setArtifactDescriptors(index.artifacts);
        setArtifactContent(Object.fromEntries(entries));
      }
    }

    loadArtifacts();
    return () => {
      cancelled = true;
    };
  }, [projectState]);

  const tabs = [
    {
      id: "state",
      label: "State",
      content: (
        <div className="ide-artifact-state">
          <div className="ide-section-title">Artifact State</div>
          {artifactDescriptors.map((artifact) => (
            <div className="ide-artifact-row" key={artifact.fileName}>
              <span>{artifact.name}</span>
              <strong>{artifact.state}</strong>
            </div>
          ))}
          {artifactDescriptors.length === 0 && (
            <div className="ide-artifact-row">
              <span>Artifacts</span>
              <strong>{getArtifactStatus(projectState)}</strong>
            </div>
          )}
          <div className="ide-muted-note">
            Raw JSON artifacts remain available in this tab group.
          </div>
        </div>
      ),
    },
    {
      id: "source",
      label: "Source",
      content: <SourceModelView vm={sourceModelVm} />,
    },
    {
      id: "workflow",
      label: "Workflow",
      content: (
        <ArtifactWorkflowView
          vm={artifactWorkflowVm}
          slotAReady={artifactDiffSlotAReady}
          slotBReady={artifactDiffSlotBReady}
          onExport={onExportArtifact}
          onImport={onImportArtifact}
          onSetDiffSlot={onSetArtifactDiffSlot}
          onCompareDiff={onCompareArtifactDiff}
          disabled={artifactOperationRunning}
        />
      ),
    },
    {
      id: "audit",
      label: "Audit",
      content: <LanguageAuditArtifactsView vm={languageAuditVm} />,
    },
    {
      id: "samples",
      label: "Samples",
      content: <SampleMetadataView vm={sampleBrowserVm} />,
    },
    {
      id: "reasoning",
      label: "Reasoning",
      content: <ReasoningOverviewView vm={reasoningOverviewVm} />,
    },
    {
      id: "ast",
      label: "AST",
      content: <JsonArtifactView data={artifactContent["ast.json"]} label="Surface AST" />,
    },
    {
      id: "semantic_ast",
      label: "Semantic AST",
      content: <JsonArtifactView data={artifactContent["semantic_ast.json"]} label="Semantic AST" />,
    },
    {
      id: "reason_ir",
      label: "Reason IR",
      content: (
        <ReasonIRView
          data={artifactContent["reason_ir.json"]}
          selectedArtifact={selectedArtifact}
          onSelectArtifact={onSelectArtifact}
        />
      ),
    },
    {
      id: "validation",
      label: "Validation",
      content: (
        <div className="ide-validation-tab-content">
          <ValidationView
            data={artifactContent["validation.json"]}
            diagnostics={(artifactContent["diagnostics.json"] as ProjectState["diagnostics"] | undefined) ?? []}
            selectedArtifact={selectedArtifact}
            onSelectArtifact={onSelectArtifact}
          />
          <JsonArtifactView data={projectValidationSummary} label="project_validation.json" />
          <JsonArtifactView data={artifactFreshnessVm} label="artifact_freshness.json" />
        </div>
      ),
    },
    {
      id: "dependency",
      label: "Dependency",
      content: (
        <DependencyGraphView
          data={(projectState?.analyzer as Record<string, unknown> | null)?.dependency_graph ?? null}
          selectedArtifact={selectedArtifact}
          onSelectArtifact={onSelectArtifact}
        />
      ),
    },
    {
      id: "raw",
      label: "All Raw",
      content: <JsonArtifactView data={projectState} label="Analyze Response" />,
    },
  ];

  return <TabPanel tabs={tabs} defaultTab="state" />;
}

interface BottomToolWindowProps extends SelectionProps {
  diagnostics: PlatformDiagnostic[];
  diagnosticsAnalysisVm: DiagnosticsAnalysisViewModel;
  artifactWorkflowVm: ArtifactWorkflowViewModel;
  languageAuditVm: LanguageAuditViewModel;
  sampleBrowserVm: SampleBrowserViewModel;
  runtimeObservabilityVm: RuntimeObservabilityViewModel;
  simulationVm: SimulationTraceViewModel;
  workspaceDiagnosticsVm: WorkspaceDiagnosticsViewModel;
  activeRelativePath?: string | null;
  projectState: ProjectState | null;
  lastError: string | null;
  activeTab?: string;
  onActiveTabChange?: (tabId: string) => void;
  onRunLanguageAudit: () => void;
  onExportLanguageAudit: () => void;
  auditOperationRunning?: boolean;
}

export function BottomToolWindow({
  diagnostics,
  diagnosticsAnalysisVm,
  artifactWorkflowVm,
  languageAuditVm,
  sampleBrowserVm,
  runtimeObservabilityVm,
  simulationVm,
  workspaceDiagnosticsVm,
  activeRelativePath,
  projectState,
  lastError,
  selectedArtifact,
  onSelectArtifact,
  activeTab,
  onActiveTabChange,
  onRunLanguageAudit,
  onExportLanguageAudit,
  auditOperationRunning,
}: BottomToolWindowProps) {
  const [problemsScope, setProblemsScope] = useState<DiagnosticScope>("all");
  const allProblems = [...diagnostics, ...workspaceDiagnosticsVm.diagnostics];
  const problemsMapping = buildFileDiagnosticsMapping(allProblems, activeRelativePath);
  const ideDiagnostics = filterByScope(problemsMapping, problemsScope);
  const logsGroups = buildLogsGroups({
    backend: projectState ? [`compiler_version=${projectState.compiler_version}`] : [],
    analyzer: workspaceDiagnosticsVm.diagnostics.map((d) => d.message),
    runtime: runtimeObservabilityVm.runtimeOutput.status !== "unavailable" ? [`runtime status: ${runtimeObservabilityVm.runtimeOutput.status}`] : [],
    ide: lastError ? [lastError] : [],
  });

  const tabs = [
    {
      id: "problems",
      label: allProblems.length > 0 ? `Problems (${allProblems.length})` : "Problems",
      content: (
        <div className="ide-problems-content">
          <div className="ide-problems-scope-filter" role="group" aria-label="Problems scope">
            {(["current", "workspace", "all"] as DiagnosticScope[]).map((scope) => (
              <button
                key={scope}
                type="button"
                onClick={() => setProblemsScope(scope)}
                aria-pressed={problemsScope === scope}
                className={problemsScope === scope ? "ide-scope-filter-active" : undefined}
              >
                {scope}
              </button>
            ))}
          </div>
          <div className="ide-muted-note">{ideDiagnostics.length} diagnostic(s) in scope: {problemsScope}</div>
          <DiagnosticsView
            diagnostics={diagnostics}
            selectedArtifact={selectedArtifact}
            onSelectArtifact={onSelectArtifact}
          />
          <DiagnosticsAnalysisView vm={diagnosticsAnalysisVm} />
        </div>
      ),
    },
    {
      id: "output",
      label: "Output",
      content: (
        <div className="ide-output-content">
          <RuntimeOutputView vm={runtimeObservabilityVm} />
          <ArtifactOperationLogsView vm={artifactWorkflowVm} />
          <LanguageAuditLogsView vm={languageAuditVm} />
          <SampleOperationLogsView vm={sampleBrowserVm} />
          <RuntimeOperationsView simulationVm={simulationVm} />
          <div className="ide-output-workspace-validation-logs">
            <div className="ide-section-title">Workspace / Project Validation Logs</div>
            {workspaceDiagnosticsVm.diagnostics.length === 0 ? (
              <div className="ide-muted-note">No workspace validation logs.</div>
            ) : (
              workspaceDiagnosticsVm.diagnostics.map((d, i) => <pre key={i}>{d.message}</pre>)
            )}
          </div>
        </div>
      ),
    },
    {
      id: "logs",
      label: "Logs",
      content: (
        <div className="ide-tool-empty">
          {lastError && <pre>{lastError}</pre>}
          {projectState && <pre>{`Last analyze: ${projectState.generated_at}\nCompiler: ${projectState.compiler_version}`}</pre>}
          {!lastError && !projectState && "No logs for this session."}
          {logsGroups.map((group) => (
            <div key={group.key} className="ide-logs-group">
              <div className="ide-section-title">{group.label}</div>
              {group.entries.length === 0 ? (
                <div className="ide-muted-note">No {group.label.toLowerCase()} logs.</div>
              ) : (
                group.entries.map((entry, i) => <pre key={i}>{entry}</pre>)
              )}
            </div>
          ))}
        </div>
      ),
    },
    {
      id: "tests",
      label: "Tests",
      content: (
        <LanguageAuditMatrixView
          vm={languageAuditVm}
          onRunAudit={onRunLanguageAudit}
          onExportAudit={onExportLanguageAudit}
          disabled={auditOperationRunning}
        />
      ),
    },
  ];

  return (
    <div className="ide-bottom-tool-window">
      <TabPanel
        tabs={tabs}
        defaultTab="problems"
        activeTab={activeTab}
        onActiveTabChange={onActiveTabChange}
      />
    </div>
  );
}
