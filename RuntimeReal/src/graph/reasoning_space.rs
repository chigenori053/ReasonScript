use crate::core::types::GraphType;
use crate::core::{
    SemanticContext, SemanticValidator, StructuralConstraintError, StructuralConstraintValidator,
};
use crate::executor::dynamics::Dynamics;
use crate::executor::ExecutionContext;
use crate::graph::ReasonGraph;
use crate::ir::GraphIR;
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet, VecDeque};
use std::fmt;
use uuid::Uuid;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SemanticPlanConstraints {
    #[serde(default)]
    pub avoid_nodes: Vec<Uuid>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub max_distance: Option<usize>,
}

impl SemanticPlanConstraints {
    pub fn none() -> Self {
        Self {
            avoid_nodes: Vec::new(),
            max_distance: None,
        }
    }
}

impl Default for SemanticPlanConstraints {
    fn default() -> Self {
        Self::none()
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SemanticPlan {
    pub start: Uuid,
    pub goal: Uuid,
    #[serde(default)]
    pub constraints: SemanticPlanConstraints,
}

impl SemanticPlan {
    pub fn new(start: Uuid, goal: Uuid) -> Self {
        Self {
            start,
            goal,
            constraints: SemanticPlanConstraints::none(),
        }
    }

    pub fn with_constraints(mut self, constraints: SemanticPlanConstraints) -> Self {
        self.constraints = constraints;
        self
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ReasoningPath {
    pub start: Uuid,
    pub goal: Uuid,
    pub nodes: Vec<Uuid>,
}

impl ReasoningPath {
    pub fn distance(&self) -> usize {
        self.nodes.len().saturating_sub(1)
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ExplorationResult {
    pub start: Uuid,
    pub reachable_nodes: Vec<Uuid>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ClosureResult {
    pub generated_relations: usize,
    pub total_relations: usize,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ReasoningSpaceError {
    InvalidGraphType(GraphType),
    InvalidStructure(StructuralConstraintError),
    InvalidSemantics(String),
    NodeNotFound(Uuid),
    GoalUnreachable { start: Uuid, goal: Uuid },
}

impl fmt::Display for ReasoningSpaceError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::InvalidGraphType(graph_type) => {
                write!(
                    formatter,
                    "reasoning space requires ReasonGraph, found {graph_type:?}"
                )
            }
            Self::InvalidStructure(error) => write!(formatter, "invalid reasoning space: {error}"),
            Self::InvalidSemantics(message) => {
                write!(formatter, "invalid reasoning space semantics: {message}")
            }
            Self::NodeNotFound(node_id) => {
                write!(formatter, "reasoning space node not found: {node_id}")
            }
            Self::GoalUnreachable { start, goal } => {
                write!(
                    formatter,
                    "semantic goal {goal} is unreachable from {start}"
                )
            }
        }
    }
}

impl std::error::Error for ReasoningSpaceError {}

impl From<StructuralConstraintError> for ReasoningSpaceError {
    fn from(error: StructuralConstraintError) -> Self {
        Self::InvalidStructure(error)
    }
}

#[derive(Debug, Clone)]
pub struct ReasoningSpace {
    graph: ReasonGraph,
}

impl ReasoningSpace {
    pub fn from_graph(graph: ReasonGraph) -> Result<Self, ReasoningSpaceError> {
        if graph.graph_type != GraphType::ReasonGraph {
            return Err(ReasoningSpaceError::InvalidGraphType(graph.graph_type));
        }
        StructuralConstraintValidator::validate_graph(&graph)?;
        Ok(Self { graph })
    }

    pub fn graph(&self) -> &ReasonGraph {
        &self.graph
    }

    pub fn into_graph(self) -> ReasonGraph {
        self.graph
    }

    pub fn semantic_unit_count(&self) -> usize {
        self.graph.states.len()
    }

    pub fn semantic_relation_count(&self) -> usize {
        self.graph.edges.len()
    }

    pub fn semantic_transition_count(&self) -> usize {
        self.graph.edges.len()
    }

    pub fn validate(&self, context: &SemanticContext) -> Result<(), ReasoningSpaceError> {
        SemanticValidator::validate_graph(&self.graph, context)
            .map_err(|error| ReasoningSpaceError::InvalidSemantics(format!("{error:?}")))
    }

    pub fn validate_structure(&self) -> Result<(), ReasoningSpaceError> {
        StructuralConstraintValidator::validate_graph(&self.graph)?;
        Ok(())
    }

    pub fn explore(&self, start: Uuid) -> Result<ExplorationResult, ReasoningSpaceError> {
        StructuralConstraintValidator::validate_graph(&self.graph)?;
        self.require_node(start)?;

        let mut adjacency: HashMap<Uuid, Vec<Uuid>> = HashMap::new();
        for edge in &self.graph.edges {
            adjacency.entry(edge.source).or_default().push(edge.target);
        }

        let mut visited = HashSet::from([start]);
        let mut queue = VecDeque::from([start]);
        let mut reachable_nodes = Vec::new();

        while let Some(current) = queue.pop_front() {
            if let Some(targets) = adjacency.get(&current) {
                for target in targets {
                    if visited.insert(*target) {
                        reachable_nodes.push(*target);
                        queue.push_back(*target);
                    }
                }
            }
        }

        Ok(ExplorationResult {
            start,
            reachable_nodes,
        })
    }

    pub fn execute_plan(&self, plan: &SemanticPlan) -> Result<ReasoningPath, ReasoningSpaceError> {
        StructuralConstraintValidator::validate_graph(&self.graph)?;
        self.require_node(plan.start)?;
        self.require_node(plan.goal)?;

        if plan.constraints.avoid_nodes.contains(&plan.start)
            || plan.constraints.avoid_nodes.contains(&plan.goal)
        {
            return Err(ReasoningSpaceError::GoalUnreachable {
                start: plan.start,
                goal: plan.goal,
            });
        }

        if plan.start == plan.goal {
            return Ok(ReasoningPath {
                start: plan.start,
                goal: plan.goal,
                nodes: vec![plan.start],
            });
        }

        let mut predecessors = HashMap::new();
        let mut visited = HashSet::from([plan.start]);
        let mut queue = VecDeque::from([(plan.start, 0usize)]);

        while let Some((current, distance)) = queue.pop_front() {
            if plan
                .constraints
                .max_distance
                .is_some_and(|maximum| distance >= maximum)
            {
                continue;
            }
            for edge in self
                .graph
                .edges
                .iter()
                .filter(|edge| edge.source == current)
            {
                if plan.constraints.avoid_nodes.contains(&edge.target) {
                    continue;
                }
                if visited.insert(edge.target) {
                    predecessors.insert(edge.target, current);
                    if edge.target == plan.goal {
                        return Ok(build_path(plan, &predecessors));
                    }
                    queue.push_back((edge.target, distance + 1));
                }
            }
        }

        Err(ReasoningSpaceError::GoalUnreachable {
            start: plan.start,
            goal: plan.goal,
        })
    }

    pub fn close(
        &mut self,
        context: &SemanticContext,
    ) -> Result<ClosureResult, ReasoningSpaceError> {
        self.validate(context)?;

        let initial_relations = self.graph.edges.len();
        let mut execution_context = ExecutionContext::new();

        loop {
            let generated = Dynamics::closure(&mut self.graph, &mut execution_context, context);
            if generated == 0 {
                break;
            }
        }

        self.validate(context)?;
        Ok(ClosureResult {
            generated_relations: self.graph.edges.len() - initial_relations,
            total_relations: self.graph.edges.len(),
        })
    }

    pub fn to_graph_ir(&self) -> GraphIR {
        GraphIR {
            graph: self.graph.clone(),
        }
    }

    fn require_node(&self, node_id: Uuid) -> Result<(), ReasoningSpaceError> {
        if self.graph.nodes.contains_key(&node_id) {
            Ok(())
        } else {
            Err(ReasoningSpaceError::NodeNotFound(node_id))
        }
    }
}

fn build_path(plan: &SemanticPlan, predecessors: &HashMap<Uuid, Uuid>) -> ReasoningPath {
    let mut nodes = vec![plan.goal];
    let mut current = plan.goal;

    while current != plan.start {
        current = predecessors[&current];
        nodes.push(current);
    }
    nodes.reverse();

    ReasoningPath {
        start: plan.start,
        goal: plan.goal,
        nodes,
    }
}
