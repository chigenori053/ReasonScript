import JsonViewer from './JsonViewer.jsx'
import ExecutionPlanPanel from './ExecutionPlanPanel.jsx'
import SimulationPanel from './SimulationPanel.jsx'
import KnowledgePanel from './KnowledgePanel.jsx'
import './TabPanel.css'

const TABS = [
  { id: 'ast',            label: 'AST',           icon: '🌳' },
  { id: 'reason_ir',      label: 'Reason IR',     icon: '⚙️' },
  { id: 'execution_plan', label: 'ExecutionPlan', icon: '📋' },
  { id: 'simulation',     label: 'Simulation',    icon: '🔄' },
  { id: 'knowledge',      label: 'Knowledge',     icon: '💡' },
  { id: 'validate',       label: 'Validation',    icon: '✔️' },
]

function getDataForTab(results, tabId) {
  if (!results) return null
  switch (tabId) {
    case 'ast':            return results.ast ?? null
    case 'reason_ir':      { const irs = results.reason_irs; return irs?.length ? (irs.length === 1 ? irs[0] : irs) : null }
    case 'execution_plan': return results.execution_plan ?? null
    case 'simulation':     return results.simulation ?? null
    case 'knowledge':      return results.knowledge ?? null
    case 'validate':       return results.validate ?? null
    default:               return null
  }
}

function TabContent({ tabId, data }) {
  switch (tabId) {
    case 'execution_plan': return <ExecutionPlanPanel data={data} />
    case 'simulation':     return <SimulationPanel data={data} />
    case 'knowledge':      return <KnowledgePanel data={data} />
    case 'ast':
    case 'reason_ir':
    case 'validate':
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
  validate:       'Validate を実行すると結果が表示されます',
}

export default function TabPanel({ results, activeView, onChangeView }) {
  const active = TABS.find(t => t.id === activeView) ?? TABS[0]
  const data = getDataForTab(results, active.id)

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
        {data ? (
          <TabContent tabId={active.id} data={data} />
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
