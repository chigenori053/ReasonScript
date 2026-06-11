use crate::decision::{
    DecisionEngine, GraphDecisionInput, GraphDecisionResult, GraphPathCandidate,
};
use crate::error::RuntimeError;
use crate::state::{HybridReasonUnit, State};
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, VecDeque};

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct GraphRelation {
    pub source: String,
    pub relation: String,
    pub target: String,
    pub expected_cost: f64,
}

impl GraphRelation {
    pub fn new(
        source: impl Into<String>,
        relation: impl Into<String>,
        target: impl Into<String>,
    ) -> Self {
        Self::with_cost(source, relation, target, 0.0)
    }

    pub fn with_cost(
        source: impl Into<String>,
        relation: impl Into<String>,
        target: impl Into<String>,
        expected_cost: f64,
    ) -> Self {
        Self {
            source: source.into(),
            relation: relation.into(),
            target: target.into(),
            expected_cost,
        }
    }

    pub fn id(&self) -> String {
        format!("{} --{}--> {}", self.source, self.relation, self.target)
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ReasonGraph {
    graph_id: String,
    nodes: BTreeMap<String, HybridReasonUnit>,
    relations: Vec<GraphRelation>,
}

impl ReasonGraph {
    pub fn new(graph_id: impl Into<String>) -> Self {
        Self {
            graph_id: graph_id.into(),
            nodes: BTreeMap::new(),
            relations: Vec::new(),
        }
    }

    pub fn graph_id(&self) -> &str {
        &self.graph_id
    }

    pub fn add_node(
        &mut self,
        node_id: impl Into<String>,
        unit: HybridReasonUnit,
    ) -> Result<(), RuntimeError> {
        let node_id = node_id.into();
        if self.nodes.contains_key(&node_id) {
            return Err(RuntimeError::GraphNodeAlreadyExists(node_id));
        }
        self.nodes.insert(node_id, unit);
        Ok(())
    }

    pub fn add_stable_node(&mut self, node_id: impl Into<String>) -> Result<(), RuntimeError> {
        let node_id = node_id.into();
        self.add_node(
            node_id.clone(),
            HybridReasonUnit::new(State::stable(node_id)),
        )
    }

    pub fn add_relation(&mut self, relation: GraphRelation) -> Result<(), RuntimeError> {
        self.require_node(&relation.source)?;
        self.require_node(&relation.target)?;
        self.relations.push(relation);
        Ok(())
    }

    pub fn node(&self, node_id: &str) -> Option<&HybridReasonUnit> {
        self.nodes.get(node_id)
    }

    pub fn node_count(&self) -> usize {
        self.nodes.len()
    }

    pub fn edge_count(&self) -> usize {
        self.relations.len()
    }

    pub fn relations(&self) -> &[GraphRelation] {
        &self.relations
    }

    pub fn has_relation(&self, source: &str, relation: &str, target: &str) -> bool {
        self.relations
            .iter()
            .any(|edge| edge.source == source && edge.relation == relation && edge.target == target)
    }

    pub fn outgoing(&self, source: &str) -> Result<Vec<&GraphRelation>, RuntimeError> {
        self.require_node(source)?;
        Ok(self
            .relations
            .iter()
            .filter(|edge| edge.source == source)
            .collect())
    }

    pub fn neighbors(&self, source: &str) -> Result<Vec<String>, RuntimeError> {
        Ok(self
            .outgoing(source)?
            .into_iter()
            .map(|edge| edge.target.clone())
            .collect())
    }

    pub fn parents(&self, node: &str) -> Result<Vec<String>, RuntimeError> {
        Ok(self
            .outgoing(node)?
            .into_iter()
            .filter(|edge| edge.relation == "IsA")
            .map(|edge| edge.target.clone())
            .collect())
    }

    pub fn children(&self, node: &str) -> Result<Vec<String>, RuntimeError> {
        self.require_node(node)?;
        Ok(self
            .relations
            .iter()
            .filter(|edge| edge.target == node && edge.relation == "IsA")
            .map(|edge| edge.source.clone())
            .collect())
    }

    pub fn find_path(&self, start: &str, target: &str) -> Result<GraphPathCandidate, RuntimeError> {
        self.require_node(start)?;
        self.require_node(target)?;
        let mut queue = VecDeque::from([GraphPathCandidate {
            nodes: vec![start.to_string()],
            edges: Vec::new(),
            total_cost: 0.0,
        }]);

        while let Some(path) = queue.pop_front() {
            let current = path.nodes.last().expect("path always has a node");
            if current == target {
                return Ok(path);
            }
            for edge in self.outgoing(current)? {
                if path.nodes.contains(&edge.target) {
                    continue;
                }
                let mut next = path.clone();
                next.nodes.push(edge.target.clone());
                next.edges.push(edge.id());
                next.total_cost += edge.expected_cost;
                queue.push_back(next);
            }
        }

        Err(RuntimeError::GraphPathNotFound {
            start: start.to_string(),
            target: target.to_string(),
        })
    }

    pub fn all_paths(
        &self,
        start: &str,
        target: &str,
    ) -> Result<Vec<GraphPathCandidate>, RuntimeError> {
        self.require_node(start)?;
        self.require_node(target)?;
        let mut paths = Vec::new();
        self.collect_paths(
            start,
            target,
            &mut vec![start.to_string()],
            &mut Vec::new(),
            0.0,
            &mut paths,
        );
        if paths.is_empty() {
            return Err(RuntimeError::GraphPathNotFound {
                start: start.to_string(),
                target: target.to_string(),
            });
        }
        Ok(paths)
    }

    fn collect_paths(
        &self,
        current: &str,
        target: &str,
        nodes: &mut Vec<String>,
        edges: &mut Vec<String>,
        total_cost: f64,
        paths: &mut Vec<GraphPathCandidate>,
    ) {
        if current == target {
            paths.push(GraphPathCandidate {
                nodes: nodes.clone(),
                edges: edges.clone(),
                total_cost,
            });
            return;
        }
        for edge in self.relations.iter().filter(|edge| edge.source == current) {
            if nodes.contains(&edge.target) {
                continue;
            }
            nodes.push(edge.target.clone());
            edges.push(edge.id());
            self.collect_paths(
                &edge.target,
                target,
                nodes,
                edges,
                total_cost + edge.expected_cost,
                paths,
            );
            edges.pop();
            nodes.pop();
        }
    }

    fn require_node(&self, node_id: &str) -> Result<(), RuntimeError> {
        if self.nodes.contains_key(node_id) {
            Ok(())
        } else {
            Err(RuntimeError::GraphNodeNotFound(node_id.to_string()))
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum GraphTraceEventKind {
    Transition,
    Reasoning,
    Decision,
    Conflict,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct GraphTraceRecord {
    pub test_id: Option<String>,
    pub graph_id: String,
    pub start_node: String,
    pub target_node: Option<String>,
    pub visited_nodes: Vec<String>,
    pub visited_edges: Vec<String>,
    pub available_paths: Vec<GraphPathCandidate>,
    pub selected_path: Option<GraphPathCandidate>,
    pub alternative_paths: Vec<GraphPathCandidate>,
    pub decision_reason: String,
    pub path_cost: Option<f64>,
    pub final_state: State,
    pub trace_event_kind: GraphTraceEventKind,
    pub policy_version: String,
    pub evaluator_version: String,
}

#[derive(Clone, Debug, Default)]
pub struct GraphTraceLogger {
    records: Vec<GraphTraceRecord>,
}

impl GraphTraceLogger {
    pub fn record(&mut self, record: GraphTraceRecord) {
        self.records.push(record);
    }

    pub fn records(&self) -> &[GraphTraceRecord] {
        &self.records
    }

    pub fn to_json_pretty(&self) -> Result<String, RuntimeError> {
        serde_json::to_string_pretty(&self.records)
            .map_err(|error| RuntimeError::TraceSerialization(error.to_string()))
    }
}

pub struct ReasonGraphRuntime {
    pub graph: ReasonGraph,
    pub decision_engine: DecisionEngine,
    pub trace_logger: GraphTraceLogger,
    pub policy_version: String,
    pub evaluator_version: String,
    current_node: String,
    trace_test_id: Option<String>,
}

impl ReasonGraphRuntime {
    pub fn new(graph: ReasonGraph, start_node: impl Into<String>) -> Result<Self, RuntimeError> {
        let start_node = start_node.into();
        graph.require_node(&start_node)?;
        Ok(Self {
            graph,
            decision_engine: DecisionEngine,
            trace_logger: GraphTraceLogger::default(),
            policy_version: "reason-graph-policy-v0.1".to_string(),
            evaluator_version: "reason-graph-evaluator-v0.1".to_string(),
            current_node: start_node,
            trace_test_id: None,
        })
    }

    pub fn set_trace_test_id(&mut self, test_id: impl Into<String>) {
        self.trace_test_id = Some(test_id.into());
    }

    pub fn current_node(&self) -> &str {
        &self.current_node
    }

    pub fn current_state(&self) -> &State {
        self.graph
            .node(&self.current_node)
            .expect("runtime current node must exist")
            .state()
    }

    pub fn transition(&mut self, relation: &str) -> Result<State, RuntimeError> {
        let start = self.current_node.clone();
        let candidates = self
            .graph
            .outgoing(&start)?
            .into_iter()
            .filter(|edge| edge.relation == relation)
            .map(path_from_edge)
            .collect::<Vec<_>>();
        let selected = if candidates.len() == 1 {
            candidates[0].clone()
        } else {
            self.select_path(&start, candidates.clone(), None)?
                .selected_path
        };
        self.apply_path(
            start,
            None,
            candidates,
            selected,
            "registered graph relation applied".to_string(),
            GraphTraceEventKind::Transition,
        )
    }

    pub fn infer_to(&mut self, target: &str) -> Result<State, RuntimeError> {
        let start = self.current_node.clone();
        let paths = self.graph.all_paths(&start, target)?;
        let decision = if paths.len() == 1 {
            GraphDecisionResult {
                selected_path: paths[0].clone(),
                alternative_paths: Vec::new(),
                decision_reason: "only available graph path".to_string(),
                path_scores: BTreeMap::from([(paths[0].id(), paths[0].total_cost)]),
                selected_to_next_score_gap: None,
            }
        } else {
            self.select_path(&start, paths.clone(), Some(target))?
        };
        self.apply_path(
            start,
            Some(target.to_string()),
            paths,
            decision.selected_path,
            decision.decision_reason,
            GraphTraceEventKind::Reasoning,
        )
    }

    pub fn decide_and_transition(&mut self) -> Result<State, RuntimeError> {
        let start = self.current_node.clone();
        let paths = self
            .graph
            .outgoing(&start)?
            .into_iter()
            .map(path_from_edge)
            .collect::<Vec<_>>();
        let decision = self.select_path(&start, paths.clone(), None)?;
        self.apply_path(
            start,
            None,
            paths,
            decision.selected_path,
            decision.decision_reason,
            GraphTraceEventKind::Decision,
        )
    }

    fn select_path(
        &mut self,
        start: &str,
        paths: Vec<GraphPathCandidate>,
        target: Option<&str>,
    ) -> Result<GraphDecisionResult, RuntimeError> {
        match self.decision_engine.decide_graph_path(GraphDecisionInput {
            source: start,
            candidates: &paths,
        }) {
            Ok(decision) => Ok(decision),
            Err(error @ RuntimeError::GraphDecisionRequired { .. }) => {
                self.record_trace(GraphTraceRecord {
                    test_id: self.trace_test_id.clone(),
                    graph_id: self.graph.graph_id().to_string(),
                    start_node: start.to_string(),
                    target_node: target.map(str::to_string),
                    visited_nodes: vec![start.to_string()],
                    visited_edges: Vec::new(),
                    available_paths: paths.clone(),
                    selected_path: None,
                    alternative_paths: paths,
                    decision_reason: "equal minimum expected graph path cost; decision required"
                        .to_string(),
                    path_cost: None,
                    final_state: self.current_state().clone(),
                    trace_event_kind: GraphTraceEventKind::Conflict,
                    policy_version: self.policy_version.clone(),
                    evaluator_version: self.evaluator_version.clone(),
                });
                Err(error)
            }
            Err(error) => Err(error),
        }
    }

    fn apply_path(
        &mut self,
        start: String,
        target: Option<String>,
        available_paths: Vec<GraphPathCandidate>,
        selected_path: GraphPathCandidate,
        decision_reason: String,
        trace_event_kind: GraphTraceEventKind,
    ) -> Result<State, RuntimeError> {
        let final_node =
            selected_path
                .nodes
                .last()
                .cloned()
                .ok_or_else(|| RuntimeError::GraphPathNotFound {
                    start: start.clone(),
                    target: target.clone().unwrap_or_else(|| "*".to_string()),
                })?;
        self.graph.require_node(&final_node)?;
        self.current_node = final_node;
        let final_state = self.current_state().clone();
        let alternative_paths = available_paths
            .iter()
            .filter(|path| **path != selected_path)
            .cloned()
            .collect();
        self.record_trace(GraphTraceRecord {
            test_id: self.trace_test_id.clone(),
            graph_id: self.graph.graph_id().to_string(),
            start_node: start,
            target_node: target,
            visited_nodes: selected_path.nodes.clone(),
            visited_edges: selected_path.edges.clone(),
            available_paths,
            selected_path: Some(selected_path.clone()),
            alternative_paths,
            decision_reason,
            path_cost: Some(selected_path.total_cost),
            final_state: final_state.clone(),
            trace_event_kind,
            policy_version: self.policy_version.clone(),
            evaluator_version: self.evaluator_version.clone(),
        });
        Ok(final_state)
    }

    fn record_trace(&mut self, record: GraphTraceRecord) {
        self.trace_logger.record(record);
    }
}

fn path_from_edge(edge: &GraphRelation) -> GraphPathCandidate {
    GraphPathCandidate {
        nodes: vec![edge.source.clone(), edge.target.clone()],
        edges: vec![edge.id()],
        total_cost: edge.expected_cost,
    }
}
