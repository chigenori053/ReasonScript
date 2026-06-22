import JsonViewer from './JsonViewer.jsx'
import ExecutionPlanPanel from './ExecutionPlanPanel.jsx'
import SimulationPanel from './SimulationPanel.jsx'
import KnowledgePanel from './KnowledgePanel.jsx'
import ValidationExplorer from './ValidationExplorer.jsx'
import ExportPanel from './ExportPanel.jsx'
import DiffPanel from './DiffPanel.jsx'
import RegressionRunner from './RegressionRunner.jsx'
import BaselinePanel from './BaselinePanel.jsx'
import OutputPanel from './OutputPanel.jsx'
import DependencyGraphPanel from './DependencyGraphPanel.jsx'
import RuntimeOperationsPanel from './RuntimeOperationsPanel.jsx'
import InputStatePanel from './InputStatePanel.jsx'
import CalculationPanel from './CalculationPanel.jsx'
import CyclePanel from './CyclePanel.jsx'
import RuntimeTracePanel from './RuntimeTracePanel.jsx'
import StrictDiagnosticsPanel from './StrictDiagnosticsPanel.jsx'
import OwnershipPanel from './OwnershipPanel.jsx'
import TypeCoveragePanel from './TypeCoveragePanel.jsx'
import ExhaustivenessPanel from './ExhaustivenessPanel.jsx'
import DeterminismPanel from './DeterminismPanel.jsx'
import ComplexityPanel from './ComplexityPanel.jsx'
import QualityDashboard from './QualityDashboard.jsx'
import './TabPanel.css'

const TABS = [
  // v0.3 tabs
  { id: 'ast',            label: 'AST',         icon: 'AST',   group: 'core' },
  { id: 'reason_ir',      label: 'Reason IR',   icon: 'IR',    group: 'core' },
  { id: 'execution_plan', label: 'ExecPlan',    icon: 'EP',    group: 'core' },
  { id: 'simulation',     label: 'Simulation',  icon: 'SIM',   group: 'core' },
  { id: 'knowledge',      label: 'Knowledge',   icon: 'K',     group: 'core' },
  { id: 'validation',     label: 'Validation',  icon: 'VAL',   group: 'core' },
  // v0.5 analysis tabs
  { id: 'output',         label: 'Output',      icon: 'OUT',   group: 'v05' },
  { id: 'dep_graph',      label: 'Dep Graph',   icon: 'DEP',   group: 'v05' },
  { id: 'runtime_ops',    label: 'Runtime',     icon: 'RUN',   group: 'v05' },
  { id: 'input_state',    label: 'Input',       icon: 'IN',    group: 'v05' },
  { id: 'calculation',    label: 'Calculation', icon: 'CALC',  group: 'v05' },
  { id: 'cycle',          label: 'Cycle',       icon: 'CYC',   group: 'v05' },
  { id: 'runtime_trace',  label: 'Trace',       icon: 'TRC',   group: 'v05' },
  { id: 'strict',         label: 'Strict',      icon: 'STR',   group: 'v05' },
  { id: 'ownership',      label: 'Ownership',   icon: 'OWN',   group: 'v05' },
  { id: 'types',          label: 'Types',       icon: 'TYP',   group: 'v05' },
  { id: 'exhaustiveness', label: 'Exhaustive',  icon: 'EXH',   group: 'v05' },
  { id: 'determinism',    label: 'Determinism', icon: 'DET',   group: 'v05' },
  { id: 'complexity',     label: 'Complexity',  icon: 'CPX',   group: 'v05' },
  { id: 'quality',        label: 'Quality',     icon: 'QUA',   group: 'v05' },
  // tooling tabs
  { id: 'artifacts',      label: 'Artifacts',   icon: 'EXP',   group: 'tool' },
  { id: 'diff',           label: 'Diff',        icon: 'DIFF',  group: 'tool' },
  { id: 'regression',     label: 'Regression',  icon: 'TEST',  group: 'tool' },
  { id: 'baseline',       label: 'Baseline',    icon: 'BASE',  group: 'tool' },
]

function getAnalysis(results, key) {
  return results?.analysis?.[key] ?? null
}

function getDataForTab(results, tabId) {
  if (!results) return null
  switch (tabId) {
    case 'ast':            return results.ast ?? null
    case 'reason_ir':      { const irs = results.reason_irs; return irs?.length ? (irs.length === 1 ? irs[0] : irs) : null }
    case 'execution_plan': return results.execution_plan ?? null
    case 'simulation':     return results.simulation ?? null
    case 'knowledge':      return results.knowledge ?? null
    case 'validation':     return results.validation ?? results.validate?.validation ?? results.validate ?? null
    case 'output':         return getAnalysis(results, 'output')
    case 'dep_graph':      return getAnalysis(results, 'dependency_graph')
    case 'runtime_ops':    return getAnalysis(results, 'runtime_operations')
    case 'input_state':    return getAnalysis(results, 'input_states')
    case 'calculation':    return getAnalysis(results, 'calculations')
    case 'cycle':          return getAnalysis(results, 'cycle_validation')
    case 'runtime_trace':  return getAnalysis(results, 'runtime_trace')
    case 'strict':         return getAnalysis(results, 'strict_diagnostics')
    case 'ownership':      return getAnalysis(results, 'ownership')
    case 'types':          return getAnalysis(results, 'type_coverage')
    case 'exhaustiveness': return getAnalysis(results, 'exhaustiveness')
    case 'determinism':    return getAnalysis(results, 'determinism')
    case 'complexity':     return getAnalysis(results, 'complexity')
    case 'quality':        return getAnalysis(results, 'quality')
    case 'artifacts':      return results.artifacts ?? results.ast ?? null
    case 'diff':           return results.diff ?? null
    case 'regression':     return results.regression ?? null
    case 'baseline':       return results.baseline_path ?? null
    default:               return null
  }
}

function TabContent({ tabId, data, controls }) {
  switch (tabId) {
    case 'execution_plan':  return <ExecutionPlanPanel data={data} />
    case 'simulation':      return <SimulationPanel data={data} />
    case 'knowledge':       return <KnowledgePanel data={data} />
    case 'validation':      return <ValidationExplorer data={data} />
    case 'output':          return <OutputPanel data={data} />
    case 'dep_graph':       return <DependencyGraphPanel data={data} />
    case 'runtime_ops':     return <RuntimeOperationsPanel data={data} />
    case 'input_state':     return <InputStatePanel data={data} />
    case 'calculation':     return <CalculationPanel data={data} />
    case 'cycle':           return <CyclePanel data={data} />
    case 'runtime_trace':   return <RuntimeTracePanel data={data} />
    case 'strict':          return <StrictDiagnosticsPanel data={data} mode={controls?.compilerMode} />
    case 'ownership':       return <OwnershipPanel data={data} />
    case 'types':           return <TypeCoveragePanel data={data} />
    case 'exhaustiveness':  return <ExhaustivenessPanel data={data} />
    case 'determinism':     return <DeterminismPanel data={data} />
    case 'complexity':      return <ComplexityPanel data={data} />
    case 'quality':         return <QualityDashboard data={data} />
    case 'artifacts':       return <ExportPanel {...controls} />
    case 'diff':            return <DiffPanel {...controls} />
    case 'regression':      return <RegressionRunner result={controls.regression} onRunAll={controls.onRunAll} disabled={controls.disabled} />
    case 'baseline':        return <BaselinePanel baselinePath={controls.baselinePath} onSaveBaseline={controls.onSaveBaseline} disabled={controls.disabled} />
    case 'ast':
    case 'reason_ir':
      return data ? <JsonViewer data={data} /> : null
    default:
      return null
  }
}

const EMPTY_HINTS = {
  ast:            'Validate または Run を実行すると AST が表示されます',
  reason_ir:      'Run を実行すると Reason IR が表示されます',
  execution_plan: 'Run を実行すると ExecutionPlan が表示されます',
  simulation:     'Run を実行すると Simulation 結果が表示されます',
  knowledge:      'Run を実行すると Knowledge が表示されます',
  validation:     'Validate または Run を実行すると Validation 結果が表示されます',
  output:         'Analyze を実行すると Output イベントが表示されます',
  dep_graph:      'Analyze を実行すると依存グラフが表示されます',
  runtime_ops:    'Analyze を実行すると Runtime Operations が表示されます',
  input_state:    'Analyze を実行すると InputState が表示されます',
  calculation:    'Analyze を実行すると Calculation が表示されます',
  cycle:          'Analyze を実行すると Cycle 検証結果が表示されます',
  runtime_trace:  'Analyze を実行すると Runtime Trace が表示されます',
  strict:         'Analyze を実行すると Strict diagnostics が表示されます',
  ownership:      'Analyze を実行すると Ownership 解析が表示されます',
  types:          'Analyze を実行すると Type Coverage が表示されます',
  exhaustiveness: 'Analyze を実行すると Exhaustiveness が表示されます',
  determinism:    'Analyze を実行すると Determinism 解析が表示されます',
  complexity:     'Analyze を実行すると Complexity レポートが表示されます',
  quality:        'Analyze を実行すると Rust Compatibility Dashboard が表示されます',
  artifacts:      'Run 後に Export/Import を実行できます',
  diff:           'Artifact A/B を設定すると差分比較できます',
  regression:     'Run All Tests で examples/ を一括実行できます',
  baseline:       'Run 後に Baseline を保存できます',
}

const GROUP_LABELS = {
  core: 'Core',
  v05: 'v0.5 Analysis',
  tool: 'Tooling',
}

export default function TabPanel({ results, activeView, onChangeView, controls }) {
  const active = TABS.find(t => t.id === activeView) ?? TABS[0]
  const data = getDataForTab(results, active.id)
  const actionTabs = new Set(['artifacts', 'diff', 'regression', 'baseline', 'strict'])

  const groups = ['core', 'v05', 'tool']

  return (
    <div className="tab-panel">
      <div className="tab-bar" style={{ flexDirection: 'column', gap: 0 }}>
        {groups.map(group => {
          const groupTabs = TABS.filter(t => t.group === group)
          return (
            <div key={group} style={{ display: 'flex', flexWrap: 'wrap', borderBottom: '1px solid #1f2937', paddingBottom: '2px', paddingTop: '2px' }}>
              <span style={{
                fontSize: '9px', color: '#4b5563', textTransform: 'uppercase',
                letterSpacing: '0.08em', padding: '4px 6px', alignSelf: 'center',
                minWidth: '56px',
              }}>{GROUP_LABELS[group]}</span>
              {groupTabs.map(tab => {
                const hasData = getDataForTab(results, tab.id) !== null
                return (
                  <button
                    key={tab.id}
                    className={`tab-btn ${activeView === tab.id ? 'active' : ''} ${hasData ? 'has-data' : ''}`}
                    onClick={() => onChangeView(tab.id)}
                    style={{ fontSize: '11px', padding: '4px 8px' }}
                  >
                    {tab.label}
                    {hasData && <span className="tab-dot" />}
                  </button>
                )
              })}
            </div>
          )
        })}
      </div>
      <div className="tab-content">
        {data || actionTabs.has(active.id) ? (
          <TabContent tabId={active.id} data={data} controls={controls} />
        ) : (
          <div className="tab-empty">
            <div className="tab-empty-icon">{active.icon}</div>
            <div className="tab-empty-msg">{EMPTY_HINTS[active.id]}</div>
          </div>
        )}
      </div>
    </div>
  )
}
