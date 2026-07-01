import TabPanel from "../components/TabPanel";
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
import DiagnosticsView from "./DiagnosticsView";
import JsonArtifactView from "./JsonArtifactView";
import PipelineOverviewView from "./PipelineOverviewView";
import ReasonIRView from "./ReasonIRView";
import RuntimeOperationsView from "./RuntimeOperationsView";
import SourceModelView from "./SourceModelView";
import ValidationView from "./ValidationView";
import type { SourceModelViewModel } from "../visualization/viewModels";

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
  onNavigate?: (stageId: string) => void;
}

export function StandardOverviewView({
  projectState,
  source,
  compilerMode,
  buildStatus,
  pipelineVm,
  knowledgeVm,
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
}

export function ArtifactsInspectorView({
  projectState,
  sourceModelVm,
  selectedArtifact,
  onSelectArtifact,
}: ArtifactsProps) {
  const artifactStateRows = [
    ["Surface AST", projectState?.surface_ast],
    ["Semantic AST", projectState?.semantic_ast],
    ["Reason IR", projectState?.reason_ir],
    ["Execution Plan", projectState?.execution_plan],
    ["Simulation", projectState?.simulation],
    ["Knowledge", projectState?.knowledge],
    ["Diagnostics", projectState?.diagnostics],
    ["Validation", projectState?.validation],
  ];

  const tabs = [
    {
      id: "state",
      label: "State",
      content: (
        <div className="ide-artifact-state">
          <div className="ide-section-title">Artifact State</div>
          {artifactStateRows.map(([label, data]) => (
            <div className="ide-artifact-row" key={label as string}>
              <span>{label as string}</span>
              <strong>{getArtifactStatus(data)}</strong>
            </div>
          ))}
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
      id: "ast",
      label: "AST",
      content: <JsonArtifactView data={projectState?.surface_ast} label="Surface AST" />,
    },
    {
      id: "semantic_ast",
      label: "Semantic AST",
      content: <JsonArtifactView data={projectState?.semantic_ast} label="Semantic AST" />,
    },
    {
      id: "reason_ir",
      label: "Reason IR",
      content: (
        <ReasonIRView
          data={projectState?.reason_ir}
          selectedArtifact={selectedArtifact}
          onSelectArtifact={onSelectArtifact}
        />
      ),
    },
    {
      id: "validation",
      label: "Validation",
      content: (
        <ValidationView
          data={projectState?.validation}
          diagnostics={projectState?.diagnostics ?? []}
          selectedArtifact={selectedArtifact}
          onSelectArtifact={onSelectArtifact}
        />
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
  simulationVm: SimulationTraceViewModel;
  projectState: ProjectState | null;
  lastError: string | null;
}

export function BottomToolWindow({
  diagnostics,
  simulationVm,
  projectState,
  lastError,
  selectedArtifact,
  onSelectArtifact,
}: BottomToolWindowProps) {
  const tabs = [
    {
      id: "problems",
      label: diagnostics.length > 0 ? `Problems (${diagnostics.length})` : "Problems",
      content: (
        <DiagnosticsView
          diagnostics={diagnostics}
          selectedArtifact={selectedArtifact}
          onSelectArtifact={onSelectArtifact}
        />
      ),
    },
    {
      id: "output",
      label: "Output",
      content: <RuntimeOperationsView simulationVm={simulationVm} />,
    },
    {
      id: "logs",
      label: "Logs",
      content: (
        <div className="ide-tool-empty">
          {lastError ? (
            <pre>{lastError}</pre>
          ) : projectState ? (
            <pre>{`Last analyze: ${projectState.generated_at}\nCompiler: ${projectState.compiler_version}`}</pre>
          ) : (
            "No logs for this session."
          )}
        </div>
      ),
    },
    {
      id: "tests",
      label: "Tests",
      content: (
        <div className="ide-tool-empty">
          No test, regression, or baseline result is attached to the current analyze result.
        </div>
      ),
    },
  ];

  return (
    <div className="ide-bottom-tool-window">
      <TabPanel tabs={tabs} defaultTab="problems" />
    </div>
  );
}
