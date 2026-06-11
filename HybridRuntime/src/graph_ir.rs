use crate::closure::{ClosureTraceEventKind, ClosureTraceRecord};
use crate::error::RuntimeError;
use crate::graph::{GraphRelation, ReasonGraph};
use crate::state::{HybridReasonUnit, State};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct GraphIRNode {
    pub node_id: String,
    pub state: State,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct GraphIRRelation {
    pub source: String,
    pub relation: String,
    pub target: String,
    pub expected_cost: f64,
}

impl GraphIRRelation {
    pub fn id(&self) -> String {
        format!("{} --{}--> {}", self.source, self.relation, self.target)
    }
}

impl From<&GraphRelation> for GraphIRRelation {
    fn from(relation: &GraphRelation) -> Self {
        Self {
            source: relation.source.clone(),
            relation: relation.relation.clone(),
            target: relation.target.clone(),
            expected_cost: relation.expected_cost,
        }
    }
}

impl From<&GraphIRRelation> for GraphRelation {
    fn from(relation: &GraphIRRelation) -> Self {
        GraphRelation::with_cost(
            &relation.source,
            &relation.relation,
            &relation.target,
            relation.expected_cost,
        )
    }
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct GraphIRClosure {
    pub closure_id: String,
    pub source_relations: Vec<GraphIRRelation>,
    pub derived_relation: GraphIRRelation,
    pub closure_level: usize,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct GraphIRProvenance {
    pub relation_id: String,
    pub ancestry: Vec<GraphIRRelation>,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct GraphIR {
    pub ir_id: String,
    pub graph_id: String,
    pub nodes: Vec<GraphIRNode>,
    pub relations: Vec<GraphIRRelation>,
    pub closures: Vec<GraphIRClosure>,
    pub provenance: Vec<GraphIRProvenance>,
}

impl GraphIR {
    pub fn to_json_pretty(&self) -> Result<String, RuntimeError> {
        serde_json::to_string_pretty(self)
            .map_err(|error| RuntimeError::TraceSerialization(error.to_string()))
    }

    pub fn mathematical_steps(&self) -> Vec<(String, String)> {
        self.closures
            .iter()
            .filter_map(|closure| {
                closure
                    .source_relations
                    .first()
                    .map(|relation| (relation.source.clone(), relation.target.clone()))
            })
            .collect()
    }
}

#[derive(Clone, Debug)]
pub struct GraphIRReconstruction {
    pub graph: ReasonGraph,
    pub closures: Vec<GraphIRClosure>,
    pub provenance: Vec<GraphIRProvenance>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum GraphIRConversionType {
    GraphToIR,
    IRToGraph,
    MathematicalToIR,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum GraphIRTraceEventKind {
    Conversion,
    Reconstruction,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct GraphIRTraceRecord {
    pub test_id: Option<String>,
    pub graph_id: String,
    pub ir_id: String,
    pub conversion_type: GraphIRConversionType,
    pub node_count: usize,
    pub relation_count: usize,
    pub closure_count: usize,
    pub provenance_count: usize,
    pub derived_relations: Vec<GraphIRRelation>,
    pub trace_event_kind: GraphIRTraceEventKind,
    pub policy_version: String,
    pub evaluator_version: String,
}

#[derive(Clone, Debug, Default)]
pub struct GraphIRTraceLogger {
    records: Vec<GraphIRTraceRecord>,
}

impl GraphIRTraceLogger {
    pub fn record(&mut self, record: GraphIRTraceRecord) {
        self.records.push(record);
    }

    pub fn records(&self) -> &[GraphIRTraceRecord] {
        &self.records
    }

    pub fn to_json_pretty(&self) -> Result<String, RuntimeError> {
        serde_json::to_string_pretty(&self.records)
            .map_err(|error| RuntimeError::TraceSerialization(error.to_string()))
    }
}

pub struct GraphIRConverter {
    pub trace_logger: GraphIRTraceLogger,
    pub policy_version: String,
    pub evaluator_version: String,
    trace_test_id: Option<String>,
    next_ir_id: usize,
}

impl Default for GraphIRConverter {
    fn default() -> Self {
        Self {
            trace_logger: GraphIRTraceLogger::default(),
            policy_version: "reason-graph-ir-policy-v0.1".to_string(),
            evaluator_version: "reason-graph-ir-evaluator-v0.1".to_string(),
            trace_test_id: None,
            next_ir_id: 1,
        }
    }
}

impl GraphIRConverter {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn set_trace_test_id(&mut self, test_id: impl Into<String>) {
        self.trace_test_id = Some(test_id.into());
    }

    pub fn graph_to_ir(
        &mut self,
        graph: &ReasonGraph,
        closure_traces: &[ClosureTraceRecord],
    ) -> GraphIR {
        let ir = GraphIR {
            ir_id: self.take_ir_id(),
            graph_id: graph.graph_id().to_string(),
            nodes: graph
                .nodes()
                .map(|(node_id, unit)| GraphIRNode {
                    node_id: node_id.to_string(),
                    state: unit.state().clone(),
                })
                .collect(),
            relations: graph
                .relations()
                .iter()
                .map(GraphIRRelation::from)
                .collect(),
            closures: closures_from_traces(closure_traces),
            provenance: provenance_from_traces(closure_traces),
        };
        self.record_conversion(
            &ir,
            GraphIRConversionType::GraphToIR,
            GraphIRTraceEventKind::Conversion,
        );
        ir
    }

    pub fn mathematical_to_ir(
        &mut self,
        graph_id: &str,
        closure_traces: &[ClosureTraceRecord],
    ) -> GraphIR {
        let closures = closures_from_traces(closure_traces);
        let mut node_states = BTreeMap::<String, State>::new();
        let mut relations = BTreeMap::<String, GraphIRRelation>::new();

        for trace in closure_traces {
            for node in &trace.visited_nodes {
                node_states
                    .entry(node.clone())
                    .or_insert_with(|| State::stable(node));
            }
            for relation in &trace.source_relations {
                let relation = GraphIRRelation::from(relation);
                relations.entry(relation.id()).or_insert(relation);
            }
        }

        let ir = GraphIR {
            ir_id: self.take_ir_id(),
            graph_id: graph_id.to_string(),
            nodes: node_states
                .into_iter()
                .map(|(node_id, state)| GraphIRNode { node_id, state })
                .collect(),
            relations: relations.into_values().collect(),
            closures,
            provenance: provenance_from_traces(closure_traces),
        };
        self.record_conversion(
            &ir,
            GraphIRConversionType::MathematicalToIR,
            GraphIRTraceEventKind::Conversion,
        );
        ir
    }

    pub fn ir_to_graph(&mut self, ir: &GraphIR) -> Result<GraphIRReconstruction, RuntimeError> {
        let mut graph = ReasonGraph::new(&ir.graph_id);
        for node in &ir.nodes {
            graph.add_node(&node.node_id, HybridReasonUnit::new(node.state.clone()))?;
        }
        for relation in &ir.relations {
            graph.add_relation(GraphRelation::from(relation))?;
        }
        self.record_conversion(
            ir,
            GraphIRConversionType::IRToGraph,
            GraphIRTraceEventKind::Reconstruction,
        );
        Ok(GraphIRReconstruction {
            graph,
            closures: ir.closures.clone(),
            provenance: ir.provenance.clone(),
        })
    }

    fn record_conversion(
        &mut self,
        ir: &GraphIR,
        conversion_type: GraphIRConversionType,
        trace_event_kind: GraphIRTraceEventKind,
    ) {
        self.trace_logger.record(GraphIRTraceRecord {
            test_id: self.trace_test_id.clone(),
            graph_id: ir.graph_id.clone(),
            ir_id: ir.ir_id.clone(),
            conversion_type,
            node_count: ir.nodes.len(),
            relation_count: ir.relations.len(),
            closure_count: ir.closures.len(),
            provenance_count: ir.provenance.len(),
            derived_relations: ir
                .closures
                .iter()
                .map(|closure| closure.derived_relation.clone())
                .collect(),
            trace_event_kind,
            policy_version: self.policy_version.clone(),
            evaluator_version: self.evaluator_version.clone(),
        });
    }

    fn take_ir_id(&mut self) -> String {
        let ir_id = format!("graph-ir-{:04}", self.next_ir_id);
        self.next_ir_id += 1;
        ir_id
    }
}

fn closures_from_traces(traces: &[ClosureTraceRecord]) -> Vec<GraphIRClosure> {
    traces
        .iter()
        .filter(|trace| {
            matches!(
                trace.trace_event_kind,
                ClosureTraceEventKind::Closure | ClosureTraceEventKind::MathematicalClosure
            )
        })
        .filter_map(|trace| {
            trace
                .derived_relation
                .as_ref()
                .map(|derived| GraphIRClosure {
                    closure_id: trace.closure_id.clone(),
                    source_relations: trace
                        .source_relations
                        .iter()
                        .map(GraphIRRelation::from)
                        .collect(),
                    derived_relation: GraphIRRelation::from(derived),
                    closure_level: trace.closure_level,
                })
        })
        .collect()
}

fn provenance_from_traces(traces: &[ClosureTraceRecord]) -> Vec<GraphIRProvenance> {
    let mut provenance = BTreeMap::<String, GraphIRProvenance>::new();
    for trace in traces {
        let Some(derived) = &trace.derived_relation else {
            continue;
        };
        if trace.closure_provenance.is_empty() {
            continue;
        }
        provenance.insert(
            derived.id(),
            GraphIRProvenance {
                relation_id: derived.id(),
                ancestry: trace
                    .closure_provenance
                    .iter()
                    .map(GraphIRRelation::from)
                    .collect(),
            },
        );
    }
    provenance.into_values().collect()
}
