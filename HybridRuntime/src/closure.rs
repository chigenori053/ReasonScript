use crate::error::RuntimeError;
use crate::graph::{GraphRelation, ReasonGraph};
use crate::state::State;
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum ClosureTraceEventKind {
    Closure,
    Saturation,
    CycleDetected,
    MathematicalClosure,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct ClosureTraceRecord {
    pub test_id: Option<String>,
    pub graph_id: String,
    pub closure_id: String,
    pub closure_level: usize,
    pub source_relations: Vec<GraphRelation>,
    pub derived_relation: Option<GraphRelation>,
    pub closure_provenance: Vec<GraphRelation>,
    pub visited_nodes: Vec<String>,
    pub visited_edges: Vec<String>,
    pub derivation_steps: Vec<String>,
    pub decision_reason: String,
    pub final_state: State,
    pub trace_event_kind: ClosureTraceEventKind,
    pub policy_version: String,
    pub evaluator_version: String,
}

#[derive(Clone, Debug, Default)]
pub struct ClosureTraceLogger {
    records: Vec<ClosureTraceRecord>,
}

impl ClosureTraceLogger {
    pub fn record(&mut self, record: ClosureTraceRecord) {
        self.records.push(record);
    }

    pub fn records(&self) -> &[ClosureTraceRecord] {
        &self.records
    }

    pub fn to_json_pretty(&self) -> Result<String, RuntimeError> {
        serde_json::to_string_pretty(&self.records)
            .map_err(|error| RuntimeError::TraceSerialization(error.to_string()))
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct ClosureResult {
    pub derived_relations: Vec<GraphRelation>,
    pub closure_levels: usize,
    pub saturated: bool,
}

pub struct GraphClosureEngine {
    pub trace_logger: ClosureTraceLogger,
    pub policy_version: String,
    pub evaluator_version: String,
    trace_test_id: Option<String>,
    next_closure_id: usize,
}

impl Default for GraphClosureEngine {
    fn default() -> Self {
        Self {
            trace_logger: ClosureTraceLogger::default(),
            policy_version: "reason-graph-closure-policy-v0.1".to_string(),
            evaluator_version: "reason-graph-closure-evaluator-v0.1".to_string(),
            trace_test_id: None,
            next_closure_id: 1,
        }
    }
}

impl GraphClosureEngine {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn set_trace_test_id(&mut self, test_id: impl Into<String>) {
        self.trace_test_id = Some(test_id.into());
    }

    pub fn derive_all(&mut self, graph: &mut ReasonGraph) -> Result<ClosureResult, RuntimeError> {
        let base_relations = graph.relations().to_vec();
        if let Some(cycle) = detect_cycle(&base_relations) {
            self.record_cycle(graph, &base_relations, cycle.clone());
            return Err(RuntimeError::GraphCycleDetected { nodes: cycle });
        }

        let relation_names = base_relations
            .iter()
            .map(|edge| edge.relation.clone())
            .collect::<BTreeSet<_>>();
        let mut derived_relations = Vec::new();

        for relation_name in &relation_names {
            let adjacency = relation_adjacency(&base_relations, relation_name);
            for source in adjacency.keys() {
                let mut path_nodes = vec![source.clone()];
                let mut path_relations = Vec::new();
                self.collect_derived_paths(
                    graph,
                    &adjacency,
                    source,
                    source,
                    relation_name,
                    &mut path_nodes,
                    &mut path_relations,
                    &mut derived_relations,
                )?;
            }
        }

        Ok(ClosureResult {
            closure_levels: usize::from(!derived_relations.is_empty()),
            saturated: derived_relations.is_empty(),
            derived_relations,
        })
    }

    pub fn derive_recursive(
        &mut self,
        graph: &mut ReasonGraph,
    ) -> Result<ClosureResult, RuntimeError> {
        let initial_relations = graph.relations().to_vec();
        if let Some(cycle) = detect_cycle(&initial_relations) {
            self.record_cycle(graph, &initial_relations, cycle.clone());
            return Err(RuntimeError::GraphCycleDetected { nodes: cycle });
        }

        let mut provenance = initial_relations
            .iter()
            .map(|edge| (relation_key(edge), vec![edge.clone()]))
            .collect::<BTreeMap<_, _>>();
        let mut all_derived = Vec::new();
        let mut closure_level = 0;

        loop {
            let snapshot = graph.relations().to_vec();
            let mut candidates = BTreeMap::<String, RecursiveCandidate>::new();

            for left in &snapshot {
                for right in snapshot
                    .iter()
                    .filter(|edge| edge.source == left.target && edge.relation == left.relation)
                {
                    if left.source == right.target
                        || graph.has_relation(&left.source, &left.relation, &right.target)
                    {
                        continue;
                    }
                    let derived = GraphRelation::new(&left.source, &left.relation, &right.target);
                    let key = relation_key(&derived);
                    let base_provenance = merge_provenance(
                        provenance
                            .get(&relation_key(left))
                            .cloned()
                            .unwrap_or_else(|| vec![left.clone()]),
                        provenance
                            .get(&relation_key(right))
                            .cloned()
                            .unwrap_or_else(|| vec![right.clone()]),
                    );
                    candidates.entry(key).or_insert_with(|| RecursiveCandidate {
                        derived,
                        immediate_sources: vec![left.clone(), right.clone()],
                        base_provenance,
                    });
                }
            }

            if candidates.is_empty() {
                self.record_saturation(graph, closure_level);
                return Ok(ClosureResult {
                    derived_relations: all_derived,
                    closure_levels: closure_level,
                    saturated: true,
                });
            }

            closure_level += 1;
            for (key, candidate) in candidates {
                graph.add_relation(candidate.derived.clone())?;
                provenance.insert(key, candidate.base_provenance.clone());
                all_derived.push(candidate.derived.clone());
                self.record_recursive_closure(graph, closure_level, candidate);
            }
        }
    }

    #[allow(clippy::too_many_arguments)]
    fn collect_derived_paths(
        &mut self,
        graph: &mut ReasonGraph,
        adjacency: &BTreeMap<String, Vec<GraphRelation>>,
        origin: &str,
        current: &str,
        relation_name: &str,
        path_nodes: &mut Vec<String>,
        path_relations: &mut Vec<GraphRelation>,
        derived_relations: &mut Vec<GraphRelation>,
    ) -> Result<(), RuntimeError> {
        let Some(outgoing) = adjacency.get(current) else {
            return Ok(());
        };

        for edge in outgoing {
            path_nodes.push(edge.target.clone());
            path_relations.push(edge.clone());

            if path_relations.len() >= 2 && !graph.has_relation(origin, relation_name, &edge.target)
            {
                let derived =
                    GraphRelation::new(origin, relation_name.to_string(), edge.target.clone());
                graph.add_relation(derived.clone())?;
                derived_relations.push(derived.clone());
                self.record_closure(graph, path_nodes, path_relations, derived);
            }

            self.collect_derived_paths(
                graph,
                adjacency,
                origin,
                &edge.target,
                relation_name,
                path_nodes,
                path_relations,
                derived_relations,
            )?;
            path_relations.pop();
            path_nodes.pop();
        }
        Ok(())
    }

    fn record_closure(
        &mut self,
        graph: &ReasonGraph,
        path_nodes: &[String],
        path_relations: &[GraphRelation],
        derived_relation: GraphRelation,
    ) {
        let closure_id = self.take_closure_id();
        self.trace_logger.record(ClosureTraceRecord {
            test_id: self.trace_test_id.clone(),
            graph_id: graph.graph_id().to_string(),
            closure_id,
            closure_level: 1,
            source_relations: path_relations.to_vec(),
            derived_relation: Some(derived_relation.clone()),
            closure_provenance: path_relations.to_vec(),
            visited_nodes: path_nodes.to_vec(),
            visited_edges: path_relations.iter().map(GraphRelation::id).collect(),
            derivation_steps: path_relations
                .iter()
                .map(|relation| relation.id())
                .chain(std::iter::once(format!("derive {}", derived_relation.id())))
                .collect(),
            decision_reason: "transitive path compressed into a derived relation".to_string(),
            final_state: graph
                .node(&derived_relation.target)
                .expect("derived relation target must exist")
                .state()
                .clone(),
            trace_event_kind: ClosureTraceEventKind::Closure,
            policy_version: self.policy_version.clone(),
            evaluator_version: self.evaluator_version.clone(),
        });
    }

    fn record_cycle(
        &mut self,
        graph: &ReasonGraph,
        relations: &[GraphRelation],
        cycle: Vec<String>,
    ) {
        let cycle_edges = cycle
            .windows(2)
            .filter_map(|nodes| {
                relations
                    .iter()
                    .find(|edge| edge.source == nodes[0] && edge.target == nodes[1])
                    .cloned()
            })
            .collect::<Vec<_>>();
        let closure_id = self.take_closure_id();
        self.trace_logger.record(ClosureTraceRecord {
            test_id: self.trace_test_id.clone(),
            graph_id: graph.graph_id().to_string(),
            closure_id,
            closure_level: 0,
            source_relations: cycle_edges.clone(),
            derived_relation: None,
            closure_provenance: cycle_edges.clone(),
            visited_nodes: cycle,
            visited_edges: cycle_edges.iter().map(GraphRelation::id).collect(),
            derivation_steps: vec!["cycle detected; closure aborted".to_string()],
            decision_reason: "cycle prevention policy stopped recursive derivation".to_string(),
            final_state: State::stable("CycleDetected"),
            trace_event_kind: ClosureTraceEventKind::CycleDetected,
            policy_version: self.policy_version.clone(),
            evaluator_version: self.evaluator_version.clone(),
        });
    }

    fn record_recursive_closure(
        &mut self,
        graph: &ReasonGraph,
        closure_level: usize,
        candidate: RecursiveCandidate,
    ) {
        let closure_id = self.take_closure_id();
        let visited_nodes = vec![
            candidate.derived.source.clone(),
            candidate.immediate_sources[0].target.clone(),
            candidate.derived.target.clone(),
        ];
        self.trace_logger.record(ClosureTraceRecord {
            test_id: self.trace_test_id.clone(),
            graph_id: graph.graph_id().to_string(),
            closure_id,
            closure_level,
            source_relations: candidate.immediate_sources.clone(),
            derived_relation: Some(candidate.derived.clone()),
            closure_provenance: candidate.base_provenance,
            visited_nodes,
            visited_edges: candidate
                .immediate_sources
                .iter()
                .map(GraphRelation::id)
                .collect(),
            derivation_steps: candidate
                .immediate_sources
                .iter()
                .map(GraphRelation::id)
                .chain(std::iter::once(format!(
                    "derive {} at closure level {closure_level}",
                    candidate.derived.id()
                )))
                .collect(),
            decision_reason: "two-edge closure reused as a recursive inference resource"
                .to_string(),
            final_state: graph
                .node(&candidate.derived.target)
                .expect("derived relation target must exist")
                .state()
                .clone(),
            trace_event_kind: ClosureTraceEventKind::Closure,
            policy_version: self.policy_version.clone(),
            evaluator_version: self.evaluator_version.clone(),
        });
    }

    fn record_saturation(&mut self, graph: &ReasonGraph, closure_level: usize) {
        let closure_id = self.take_closure_id();
        self.trace_logger.record(ClosureTraceRecord {
            test_id: self.trace_test_id.clone(),
            graph_id: graph.graph_id().to_string(),
            closure_id,
            closure_level,
            source_relations: Vec::new(),
            derived_relation: None,
            closure_provenance: Vec::new(),
            visited_nodes: Vec::new(),
            visited_edges: Vec::new(),
            derivation_steps: vec!["no new closure candidates".to_string()],
            decision_reason: "graph closure reached a fixed point".to_string(),
            final_state: State::stable("No New Closure"),
            trace_event_kind: ClosureTraceEventKind::Saturation,
            policy_version: self.policy_version.clone(),
            evaluator_version: self.evaluator_version.clone(),
        });
    }

    fn take_closure_id(&mut self) -> String {
        let id = format!("closure-{:04}", self.next_closure_id);
        self.next_closure_id += 1;
        id
    }
}

struct RecursiveCandidate {
    derived: GraphRelation,
    immediate_sources: Vec<GraphRelation>,
    base_provenance: Vec<GraphRelation>,
}

fn relation_key(relation: &GraphRelation) -> String {
    relation.id()
}

fn merge_provenance(mut left: Vec<GraphRelation>, right: Vec<GraphRelation>) -> Vec<GraphRelation> {
    for relation in right {
        if !left
            .iter()
            .any(|existing| relation_key(existing) == relation_key(&relation))
        {
            left.push(relation);
        }
    }
    left
}

fn relation_adjacency(
    relations: &[GraphRelation],
    relation_name: &str,
) -> BTreeMap<String, Vec<GraphRelation>> {
    let mut adjacency = BTreeMap::<String, Vec<GraphRelation>>::new();
    for relation in relations
        .iter()
        .filter(|edge| edge.relation == relation_name)
    {
        adjacency
            .entry(relation.source.clone())
            .or_default()
            .push(relation.clone());
    }
    adjacency
}

fn detect_cycle(relations: &[GraphRelation]) -> Option<Vec<String>> {
    let mut adjacency = BTreeMap::<String, Vec<String>>::new();
    for relation in relations {
        adjacency
            .entry(relation.source.clone())
            .or_default()
            .push(relation.target.clone());
    }
    let mut visited = BTreeSet::new();
    let mut active = BTreeSet::new();
    let mut path = Vec::new();
    for node in adjacency.keys() {
        if let Some(cycle) = cycle_from(node, &adjacency, &mut visited, &mut active, &mut path) {
            return Some(cycle);
        }
    }
    None
}

fn cycle_from(
    node: &str,
    adjacency: &BTreeMap<String, Vec<String>>,
    visited: &mut BTreeSet<String>,
    active: &mut BTreeSet<String>,
    path: &mut Vec<String>,
) -> Option<Vec<String>> {
    if active.contains(node) {
        let start = path.iter().position(|item| item == node).unwrap_or(0);
        let mut cycle = path[start..].to_vec();
        cycle.push(node.to_string());
        return Some(cycle);
    }
    if !visited.insert(node.to_string()) {
        return None;
    }
    active.insert(node.to_string());
    path.push(node.to_string());
    if let Some(neighbors) = adjacency.get(node) {
        for neighbor in neighbors {
            if let Some(cycle) = cycle_from(neighbor, adjacency, visited, active, path) {
                return Some(cycle);
            }
        }
    }
    path.pop();
    active.remove(node);
    None
}

#[derive(Clone, Debug, PartialEq)]
pub struct MathValue {
    pub value: f64,
    pub unit: Option<String>,
}

impl MathValue {
    pub fn scalar(value: f64) -> Self {
        Self { value, unit: None }
    }

    pub fn with_unit(value: f64, unit: impl Into<String>) -> Self {
        Self {
            value,
            unit: Some(unit.into()),
        }
    }

    fn label(&self) -> String {
        let value = format_number(self.value);
        match &self.unit {
            Some(unit) => format!("{value} {unit}"),
            None => value,
        }
    }
}

pub struct MathClosureEngine {
    pub trace_logger: ClosureTraceLogger,
    pub policy_version: String,
    pub evaluator_version: String,
    trace_test_id: Option<String>,
    next_closure_id: usize,
    provenance_by_graph: BTreeMap<String, Vec<GraphRelation>>,
}

impl Default for MathClosureEngine {
    fn default() -> Self {
        Self {
            trace_logger: ClosureTraceLogger::default(),
            policy_version: "math-closure-policy-v0.1".to_string(),
            evaluator_version: "math-closure-evaluator-v0.1".to_string(),
            trace_test_id: None,
            next_closure_id: 1,
            provenance_by_graph: BTreeMap::new(),
        }
    }
}

impl MathClosureEngine {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn set_trace_test_id(&mut self, test_id: impl Into<String>) {
        self.trace_test_id = Some(test_id.into());
    }

    pub fn add(
        &mut self,
        graph_id: &str,
        left: MathValue,
        right: MathValue,
    ) -> Result<MathValue, RuntimeError> {
        if left.unit != right.unit {
            return Err(RuntimeError::UnitMismatch {
                left: left.unit.unwrap_or_else(|| "scalar".to_string()),
                right: right.unit.unwrap_or_else(|| "scalar".to_string()),
            });
        }
        let result = MathValue {
            value: left.value + right.value,
            unit: left.unit.clone(),
        };
        let expression = format!("{} + {}", left.label(), right.label());
        self.record_math(
            graph_id,
            expression.clone(),
            result.clone(),
            vec![expression, result.label()],
            "addition closure evaluated",
        );
        Ok(result)
    }

    pub fn multiply(
        &mut self,
        graph_id: &str,
        left: MathValue,
        right: MathValue,
    ) -> Result<MathValue, RuntimeError> {
        if left.unit.is_some() && right.unit.is_some() {
            return Err(RuntimeError::InvalidMathematicalExpression(
                "multiplication of two unit-bearing values is outside Phase 1".to_string(),
            ));
        }
        let unit = left.unit.clone().or(right.unit.clone());
        let result = MathValue {
            value: left.value * right.value,
            unit,
        };
        let expression = format!("{} * {}", left.label(), right.label());
        self.record_math(
            graph_id,
            expression.clone(),
            result.clone(),
            vec![expression, result.label()],
            "multiplication closure evaluated",
        );
        Ok(result)
    }

    pub fn subtract(
        &mut self,
        graph_id: &str,
        left: MathValue,
        right: MathValue,
    ) -> Result<MathValue, RuntimeError> {
        if left.unit != right.unit {
            return Err(RuntimeError::UnitMismatch {
                left: left.unit.unwrap_or_else(|| "scalar".to_string()),
                right: right.unit.unwrap_or_else(|| "scalar".to_string()),
            });
        }
        let result = MathValue {
            value: left.value - right.value,
            unit: left.unit.clone(),
        };
        let expression = format!("{} - {}", left.label(), right.label());
        self.record_math(
            graph_id,
            expression.clone(),
            result.clone(),
            vec![expression, result.label()],
            "subtraction reused the preceding mathematical state",
        );
        Ok(result)
    }

    pub fn solve_linear(
        &mut self,
        graph_id: &str,
        coefficient: f64,
        constant: f64,
        rhs: f64,
    ) -> Result<MathValue, RuntimeError> {
        if coefficient == 0.0 {
            return Err(RuntimeError::InvalidMathematicalExpression(
                "linear coefficient must be non-zero".to_string(),
            ));
        }
        let isolated = rhs - constant;
        let result = MathValue::scalar(isolated / coefficient);
        let initial = if coefficient == 1.0 {
            format!("x + {} = {}", format_number(constant), format_number(rhs))
        } else {
            format!(
                "{}x + {} = {}",
                format_number(coefficient),
                format_number(constant),
                format_number(rhs)
            )
        };
        let middle = if coefficient == 1.0 {
            format!("x = {}", format_number(isolated))
        } else {
            format!(
                "{}x = {}",
                format_number(coefficient),
                format_number(isolated)
            )
        };
        let final_step = format!("x = {}", result.label());
        self.record_math(
            graph_id,
            initial.clone(),
            result.clone(),
            vec![initial, middle, final_step],
            "inverse operations isolated the unknown",
        );
        Ok(result)
    }

    pub fn solve_linear_recursive(
        &mut self,
        graph_id: &str,
        coefficient: f64,
        constant: f64,
        rhs: f64,
    ) -> Result<MathValue, RuntimeError> {
        if coefficient == 0.0 {
            return Err(RuntimeError::InvalidMathematicalExpression(
                "linear coefficient must be non-zero".to_string(),
            ));
        }
        let initial = format!(
            "{}x + {} = {}",
            format_number(coefficient),
            format_number(constant),
            format_number(rhs)
        );
        let isolated = rhs - constant;
        let intermediate = format!(
            "{}x = {}",
            format_number(coefficient),
            format_number(isolated)
        );
        self.record_math_transition(
            graph_id,
            initial,
            intermediate.clone(),
            "subtraction isolated the variable term",
        );

        let result = MathValue::scalar(isolated / coefficient);
        self.record_math_transition(
            graph_id,
            intermediate,
            format!("x = {}", result.label()),
            "division reused the derived intermediate state",
        );
        Ok(result)
    }

    fn record_math(
        &mut self,
        graph_id: &str,
        expression: String,
        result: MathValue,
        derivation_steps: Vec<String>,
        decision_reason: &str,
    ) {
        let source = GraphRelation::new(expression.clone(), "Evaluates", result.label());
        let derived = GraphRelation::new(expression.clone(), "EvaluatesTo", result.label());
        let closure_level = self.next_math_level(graph_id);
        let closure_provenance = self.extend_math_provenance(graph_id, source.clone());
        self.trace_logger.record(ClosureTraceRecord {
            test_id: self.trace_test_id.clone(),
            graph_id: graph_id.to_string(),
            closure_id: format!("math-closure-{:04}", self.next_closure_id),
            closure_level,
            source_relations: vec![source.clone()],
            derived_relation: Some(derived),
            closure_provenance,
            visited_nodes: vec![expression, result.label()],
            visited_edges: vec![source.id()],
            derivation_steps,
            decision_reason: decision_reason.to_string(),
            final_state: State::stable(result.label()),
            trace_event_kind: ClosureTraceEventKind::MathematicalClosure,
            policy_version: self.policy_version.clone(),
            evaluator_version: self.evaluator_version.clone(),
        });
        self.next_closure_id += 1;
    }

    fn record_math_transition(
        &mut self,
        graph_id: &str,
        source_state: String,
        target_state: String,
        decision_reason: &str,
    ) {
        let source = GraphRelation::new(&source_state, "TransformsTo", &target_state);
        let closure_level = self.next_math_level(graph_id);
        let closure_provenance = self.extend_math_provenance(graph_id, source.clone());
        self.trace_logger.record(ClosureTraceRecord {
            test_id: self.trace_test_id.clone(),
            graph_id: graph_id.to_string(),
            closure_id: format!("math-closure-{:04}", self.next_closure_id),
            closure_level,
            source_relations: vec![source.clone()],
            derived_relation: Some(source.clone()),
            closure_provenance,
            visited_nodes: vec![source_state.clone(), target_state.clone()],
            visited_edges: vec![source.id()],
            derivation_steps: vec![source_state, target_state.clone()],
            decision_reason: decision_reason.to_string(),
            final_state: State::stable(target_state),
            trace_event_kind: ClosureTraceEventKind::MathematicalClosure,
            policy_version: self.policy_version.clone(),
            evaluator_version: self.evaluator_version.clone(),
        });
        self.next_closure_id += 1;
    }

    fn next_math_level(&self, graph_id: &str) -> usize {
        self.provenance_by_graph
            .get(graph_id)
            .map_or(1, |provenance| provenance.len() + 1)
    }

    fn extend_math_provenance(
        &mut self,
        graph_id: &str,
        source: GraphRelation,
    ) -> Vec<GraphRelation> {
        let provenance = self
            .provenance_by_graph
            .entry(graph_id.to_string())
            .or_default();
        provenance.push(source);
        provenance.clone()
    }
}

fn format_number(value: f64) -> String {
    if value.fract() == 0.0 {
        format!("{value:.0}")
    } else {
        value.to_string()
    }
}
