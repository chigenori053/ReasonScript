use crate::core::types::{RelationType, TransitionType};
use crate::graph::{
    ReasonGraph, ReasoningSpace, ReasoningSpaceError, SemanticPlan, SemanticPlanConstraints,
};
use serde::{Deserialize, Serialize};
use std::fmt;
use uuid::Uuid;

pub const SEMANTIC_SIMULATION_VERSION: &str = "ssv-1/0.1-draft";

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SimulationStep {
    pub source: Uuid,
    pub target: Uuid,
    pub relation: RelationType,
    pub transition: TransitionType,
    pub cost: f64,
    pub confidence: f64,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SimulationTrace {
    pub states: Vec<Uuid>,
    pub steps: Vec<SimulationStep>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SimulationResult {
    pub success: bool,
    pub path: Vec<Uuid>,
    pub distance: usize,
    pub cost: f64,
    pub confidence: f64,
    pub trace: SimulationTrace,
    pub predicted_states: Vec<Uuid>,
}

impl SimulationResult {
    pub fn to_json_pretty(&self) -> Result<String, SemanticSimulationError> {
        serde_json::to_string_pretty(self)
            .map_err(|error| SemanticSimulationError::Serialization(error.to_string()))
    }
}

#[derive(Debug, Clone, PartialEq)]
pub enum SemanticSimulationError {
    InvalidReasoningSpace(String),
    NodeNotFound(Uuid),
    InvalidPath { source: Uuid, target: Uuid },
    InvalidEdgeCost { edge_id: Uuid, cost: f64 },
    InvalidEdgeConfidence { edge_id: Uuid, confidence: f64 },
    Serialization(String),
}

impl fmt::Display for SemanticSimulationError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::InvalidReasoningSpace(message) => {
                write!(
                    formatter,
                    "semantic simulation rejected reasoning space: {message}"
                )
            }
            Self::NodeNotFound(node_id) => {
                write!(formatter, "semantic simulation node not found: {node_id}")
            }
            Self::InvalidPath { source, target } => {
                write!(
                    formatter,
                    "semantic simulation path has no relation from {source} to {target}"
                )
            }
            Self::InvalidEdgeCost { edge_id, cost } => {
                write!(
                    formatter,
                    "edge {edge_id} has invalid simulation cost {cost}"
                )
            }
            Self::InvalidEdgeConfidence {
                edge_id,
                confidence,
            } => {
                write!(
                    formatter,
                    "edge {edge_id} has invalid simulation confidence {confidence}"
                )
            }
            Self::Serialization(message) => {
                write!(
                    formatter,
                    "semantic simulation serialization failed: {message}"
                )
            }
        }
    }
}

impl std::error::Error for SemanticSimulationError {}

#[derive(Debug, Clone, Default)]
pub struct SemanticSimulation;

impl SemanticSimulation {
    pub fn new() -> Self {
        Self
    }

    pub fn simulate(
        &self,
        space: &ReasoningSpace,
        plan: &SemanticPlan,
    ) -> Result<SimulationResult, SemanticSimulationError> {
        self.validate_space(space)?;
        self.require_node(space, plan.start)?;
        self.require_node(space, plan.goal)?;

        let predicted_states = self.predict(space, plan.start)?;
        let path = match space.execute_plan(plan) {
            Ok(path) => path.nodes,
            Err(ReasoningSpaceError::GoalUnreachable { .. }) => {
                return Ok(SimulationResult {
                    success: false,
                    path: vec![plan.start],
                    distance: 0,
                    cost: 0.0,
                    confidence: 0.0,
                    trace: SimulationTrace {
                        states: vec![plan.start],
                        steps: Vec::new(),
                    },
                    predicted_states,
                });
            }
            Err(error) => return Err(map_space_error(error)),
        };

        let mut steps = Vec::with_capacity(path.len().saturating_sub(1));
        let mut cost = 0.0;
        let mut confidence = 1.0;

        for nodes in path.windows(2) {
            let edge = space
                .graph()
                .edges
                .iter()
                .find(|edge| edge.source == nodes[0] && edge.target == nodes[1])
                .ok_or(SemanticSimulationError::InvalidPath {
                    source: nodes[0],
                    target: nodes[1],
                })?;
            validate_edge_metrics(edge.id, edge.cost, edge.confidence)?;
            cost += edge.cost;
            confidence *= edge.confidence;
            steps.push(SimulationStep {
                source: edge.source,
                target: edge.target,
                relation: edge.relation,
                transition: edge.transition.transition_type,
                cost: edge.cost,
                confidence: edge.confidence,
            });
        }

        Ok(SimulationResult {
            success: true,
            distance: path.len().saturating_sub(1),
            cost,
            confidence,
            trace: SimulationTrace {
                states: path.clone(),
                steps,
            },
            predicted_states: path.iter().copied().skip(1).collect(),
            path,
        })
    }

    pub fn simulate_graph(
        &self,
        graph: &ReasonGraph,
        plan: &SemanticPlan,
    ) -> Result<SimulationResult, SemanticSimulationError> {
        let space = ReasoningSpace::from_graph(graph.clone())
            .map_err(|error| SemanticSimulationError::InvalidReasoningSpace(error.to_string()))?;
        self.simulate(&space, plan)
    }

    pub fn simulate_goal(
        &self,
        space: &ReasoningSpace,
        start: Uuid,
        goal: Uuid,
    ) -> Result<SimulationResult, SemanticSimulationError> {
        self.simulate(space, &SemanticPlan::new(start, goal))
    }

    pub fn simulate_goal_with_constraints(
        &self,
        space: &ReasoningSpace,
        start: Uuid,
        goal: Uuid,
        constraints: SemanticPlanConstraints,
    ) -> Result<SimulationResult, SemanticSimulationError> {
        self.simulate(
            space,
            &SemanticPlan::new(start, goal).with_constraints(constraints),
        )
    }

    pub fn predict(
        &self,
        space: &ReasoningSpace,
        current: Uuid,
    ) -> Result<Vec<Uuid>, SemanticSimulationError> {
        self.validate_space(space)?;
        self.require_node(space, current)?;
        space
            .explore(current)
            .map(|result| result.reachable_nodes)
            .map_err(map_space_error)
    }

    fn validate_space(&self, space: &ReasoningSpace) -> Result<(), SemanticSimulationError> {
        space
            .validate_structure()
            .map_err(|error| SemanticSimulationError::InvalidReasoningSpace(error.to_string()))?;
        for edge in &space.graph().edges {
            validate_edge_metrics(edge.id, edge.cost, edge.confidence)?;
        }
        Ok(())
    }

    fn require_node(
        &self,
        space: &ReasoningSpace,
        node_id: Uuid,
    ) -> Result<(), SemanticSimulationError> {
        if space.graph().nodes.contains_key(&node_id) {
            Ok(())
        } else {
            Err(SemanticSimulationError::NodeNotFound(node_id))
        }
    }
}

fn validate_edge_metrics(
    edge_id: Uuid,
    cost: f64,
    confidence: f64,
) -> Result<(), SemanticSimulationError> {
    if !cost.is_finite() || cost < 0.0 {
        return Err(SemanticSimulationError::InvalidEdgeCost { edge_id, cost });
    }
    if !confidence.is_finite() || !(0.0..=1.0).contains(&confidence) {
        return Err(SemanticSimulationError::InvalidEdgeConfidence {
            edge_id,
            confidence,
        });
    }
    Ok(())
}

fn map_space_error(error: ReasoningSpaceError) -> SemanticSimulationError {
    match error {
        ReasoningSpaceError::NodeNotFound(node_id) => {
            SemanticSimulationError::NodeNotFound(node_id)
        }
        other => SemanticSimulationError::InvalidReasoningSpace(other.to_string()),
    }
}
