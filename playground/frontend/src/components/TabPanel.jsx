import JsonViewer from './JsonViewer.jsx'
import ExecutionPlanPanel from './ExecutionPlanPanel.jsx'
import SimulationPanel from './SimulationPanel.jsx'
import KnowledgePanel from './KnowledgePanel.jsx'
import ValidationExplorer from './ValidationExplorer.jsx'
import ExportPanel from './ExportPanel.jsx'
import DiffPanel from './DiffPanel.jsx'
import RegressionRunner from './RegressionRunner.jsx'
import BaselinePanel from './BaselinePanel.jsx'
import './TabPanel.css'

const TABS = [
  { id: 'ast',            label: 'AST',            icon: 'AST' },
  { id: 'reason_ir',      label: 'Reason IR',      icon: 'IR' },
  { id: 'execution_plan', label: 'ExecutionPlan',  icon: 'EP' },
  { id: 'simulation',     label: 'Simulation',     icon: 'SIM' },
  { id: 'knowledge',      label: 'Knowledge',      icon: 'K' },
  { id: 'validation',     label: 'Validation',     icon: 'VAL' },
  { id: 'artifacts',      label: 'Artifacts',      icon: 'EXP' },
  { id: 'diff',           label: 'Diff',           icon: 'DIFF' },
  { id: 'regression',     label: 'Regression',     icon: 'TEST' },
  { id: 'baseline',       label: 'Baseline',       icon: 'BASE' },
]

function getDataForTab(results, tabId) {
  if (!results) return null
  switch (tabId) {
    case 'ast':            return results.ast ?? null
    case 'reason_ir':      { const irs = results.reason_irs; return irs?.length ? (irs.length === 1 ? irs[0] : irs) : null }
    case 'execution_plan': return results.execution_plan ?? null
    case 'simulation':     return results.simulation ?? null
    case 'knowledge':      return results.knowledge ?? null
    case 'validation':     return results.validation ?? results.validate?.validation ?? results.validate ?? null
    case 'artifacts':      return results.artifacts ?? results.ast ?? null
    case 'diff':           return results.diff ?? null
    case 'regression':     return results.regression ?? null
    case 'baseline':       return results.baseline_path ?? null
    default:               return null
  }
}

function TabContent({ tabId, data, controls }) {
  switch (tabId) {
    case 'execution_plan': return <ExecutionPlanPanel data={data} />
    case 'simulation':     return <SimulationPanel data={data} />
    case 'knowledge':      return <KnowledgePanel data={data} />
    case 'validation':     return <ValidationExplorer data={data} />
    case 'artifacts':      return <ExportPanel {...controls} />
    case 'diff':           return <DiffPanel {...controls} />
    case 'regression':     return <RegressionRunner result={controls.regression} onRunAll={controls.onRunAll} disabled={controls.disabled} />
    case 'baseline':       return <BaselinePanel baselinePath={controls.baselinePath} onSaveBaseline={controls.onSaveBaseline} disabled={controls.disabled} />
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
  artifacts:      'Run 後に Export/Import を実行できます',
  diff:           'Artifact A/B を設定すると差分比較できます',
  regression:     'Run All Tests で examples/ を一括実行できます',
  baseline:       'Run 後に Baseline を保存できます',
}

export default function TabPanel({ results, activeView, onChangeView, controls }) {
  const active = TABS.find(t => t.id === activeView) ?? TABS[0]
  const data = getDataForTab(results, active.id)
  const actionTabs = new Set(['artifacts', 'diff', 'regression', 'baseline'])

  return (
    <div className="tab-panel">
      <div className="tab-bar">
        {TABS.map(tab => {
          const hasData = getDataForTab(results, tab.id) !== null
          return (
            <button
              key={tab.id}
              className={`tab-btn ${activeView === tab.id ? 'active' : ''} ${hasData ? 'has-data' : ''}`}
              onClick={() => onChangeView(tab.id)}
            >
              {tab.label}
              {hasData && <span className="tab-dot" />}
            </button>
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
