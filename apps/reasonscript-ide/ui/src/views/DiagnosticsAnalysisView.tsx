import type {
  AnalysisDiagnostic,
  DiagnosticsAnalysisViewModel,
} from "../viewModels/analysisDiagnostics";

interface Section {
  id: string;
  title: string;
  status: string;
  diagnostics: AnalysisDiagnostic[];
  empty: string;
}

function severityClass(severity: string) {
  if (severity === "error") return "ide-analysis-severity error";
  if (severity === "warning") return "ide-analysis-severity warning";
  return "ide-analysis-severity info";
}

function DiagnosticRow({ diagnostic }: { diagnostic: AnalysisDiagnostic }) {
  return (
    <div className="ide-analysis-diagnostic-row">
      <span className={severityClass(diagnostic.severity)}>{diagnostic.severity}</span>
      <span className="ide-analysis-feature">{diagnostic.feature}</span>
      {diagnostic.code && <span className="ide-analysis-code">{diagnostic.code}</span>}
      {diagnostic.stage && <span className="ide-analysis-stage">{diagnostic.stage}</span>}
      {diagnostic.relativePath && <span className="ide-analysis-path">{diagnostic.relativePath}</span>}
      <span className="ide-analysis-message">{diagnostic.message}</span>
    </div>
  );
}

function AnalysisSection({ section }: { section: Section }) {
  return (
    <section className="ide-analysis-section" data-analysis-section={section.id}>
      <div className="ide-analysis-section-title">
        <span>{section.title}</span>
        <strong>{section.status}</strong>
      </div>
      {section.diagnostics.length > 0 ? (
        section.diagnostics.map((diagnostic) => (
          <DiagnosticRow diagnostic={diagnostic} key={diagnostic.id} />
        ))
      ) : (
        <div className="ide-analysis-empty">{section.empty}</div>
      )}
    </section>
  );
}

export default function DiagnosticsAnalysisView({
  vm,
}: {
  vm: DiagnosticsAnalysisViewModel;
}) {
  const sections: Section[] = [
    {
      id: "strict-diagnostics",
      title: "Strict diagnostics",
      status: vm.strict.status,
      diagnostics: vm.strict.diagnostics,
      empty: vm.strict.status === "unavailable"
        ? "Strict diagnostics unavailable."
        : "No strict diagnostics reported.",
    },
    {
      id: "cycle-diagnostics",
      title: "Cycle diagnostics",
      status: vm.cycle.status,
      diagnostics: vm.cycle.diagnostics,
      empty: vm.cycle.status === "unavailable"
        ? "Cycle diagnostics unavailable."
        : "No cycle diagnostics reported.",
    },
    {
      id: "exhaustiveness",
      title: "Exhaustiveness",
      status: vm.exhaustiveness.status,
      diagnostics: vm.exhaustiveness.diagnostics,
      empty: vm.exhaustiveness.status === "unavailable"
        ? "No exhaustiveness data available."
        : "No exhaustiveness diagnostics reported.",
    },
    {
      id: "type-coverage",
      title: "Type coverage",
      status: vm.typeCoverage.status,
      diagnostics: vm.typeCoverage.diagnostics,
      empty: vm.typeCoverage.status === "unavailable"
        ? "Type coverage unavailable."
        : "No type coverage diagnostics reported.",
    },
    {
      id: "ownership-analysis",
      title: "Ownership analysis",
      status: vm.ownership.status,
      diagnostics: vm.ownership.diagnostics,
      empty: vm.ownership.status === "unavailable"
        ? "Ownership analysis unavailable."
        : "No ownership diagnostics reported.",
    },
    {
      id: "determinism",
      title: "Determinism",
      status: vm.determinism.status,
      diagnostics: vm.determinism.diagnostics,
      empty: vm.determinism.status === "unavailable"
        ? "Determinism data unavailable."
        : "No determinism diagnostics reported.",
    },
    {
      id: "complexity",
      title: "Complexity",
      status: vm.complexity.status,
      diagnostics: vm.complexity.diagnostics,
      empty: vm.complexity.status === "unavailable"
        ? "Complexity metrics unavailable."
        : "No complexity diagnostics reported.",
    },
  ];

  return (
    <div className="ide-analysis-diagnostics" data-problems-analysis="phase-4-5-c2-a">
      {sections.map((section) => (
        <AnalysisSection section={section} key={section.id} />
      ))}
    </div>
  );
}
