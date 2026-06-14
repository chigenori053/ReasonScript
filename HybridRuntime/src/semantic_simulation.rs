use crate::semantic_planning::{SemanticPlan, SemanticPlanningEngine, SemanticPlanningError};
use crate::semantic_transformation::{SemanticTransformationEngine, SemanticTransformationError};
use crate::semantic_type::SemanticTypeId;
use serde::{Deserialize, Serialize};
use std::fmt;

pub const SEMANTIC_SIMULATION_VERSION: &str = "semantic-simulation-engine/0.1";
pub const SIMULATION_TRACE_NODE: &str = "SimulationTrace";
pub const SIMULATION_RESULT_NODE: &str = "SimulationResult";

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SimulationState {
    pub current: SemanticTypeId,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SimulationStep {
    pub source: SemanticTypeId,
    pub target: SemanticTypeId,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SimulationTrace {
    pub states: Vec<SemanticTypeId>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SimulationResult {
    pub initial_state: SemanticTypeId,
    pub final_state: SemanticTypeId,
    pub trace: SimulationTrace,
    pub distance: usize,
    pub reachable: bool,
}

impl SimulationResult {
    pub fn to_json_pretty(&self) -> Result<String, SemanticSimulationError> {
        serde_json::to_string_pretty(self)
            .map_err(|error| SemanticSimulationError::Serialization(error.to_string()))
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SimulationTraceIrNode {
    pub node_type: String,
    pub states: Vec<SemanticTypeId>,
}

impl From<&SimulationTrace> for SimulationTraceIrNode {
    fn from(trace: &SimulationTrace) -> Self {
        Self {
            node_type: SIMULATION_TRACE_NODE.to_string(),
            states: trace.states.clone(),
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SimulationResultIrNode {
    pub node_type: String,
    pub final_state: SemanticTypeId,
    pub distance: usize,
    pub reachable: bool,
}

impl From<&SimulationResult> for SimulationResultIrNode {
    fn from(result: &SimulationResult) -> Self {
        Self {
            node_type: SIMULATION_RESULT_NODE.to_string(),
            final_state: result.final_state.clone(),
            distance: result.distance,
            reachable: result.reachable,
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum SemanticSimulationError {
    Planning(SemanticPlanningError),
    Transformation(SemanticTransformationError),
    InvalidStep {
        source: String,
        target: String,
        distance: usize,
    },
    Serialization(String),
}

impl fmt::Display for SemanticSimulationError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Planning(error) => write!(formatter, "semantic simulation planning failed: {error}"),
            Self::Transformation(error) => {
                write!(formatter, "semantic simulation transformation failed: {error}")
            }
            Self::InvalidStep {
                source,
                target,
                distance,
            } => write!(
                formatter,
                "semantic simulation step {source} -> {target} is not direct; distance is {distance}"
            ),
            Self::Serialization(message) => {
                write!(formatter, "semantic simulation serialization failed: {message}")
            }
        }
    }
}

impl std::error::Error for SemanticSimulationError {}

#[derive(Clone, Debug)]
pub struct SemanticSimulationEngine {
    planning_engine: SemanticPlanningEngine,
    transformation_engine: SemanticTransformationEngine,
}

impl SemanticSimulationEngine {
    pub fn new(
        planning_engine: SemanticPlanningEngine,
        transformation_engine: SemanticTransformationEngine,
    ) -> Self {
        Self {
            planning_engine,
            transformation_engine,
        }
    }

    pub fn planning_engine(&self) -> &SemanticPlanningEngine {
        &self.planning_engine
    }

    pub fn transformation_engine(&self) -> &SemanticTransformationEngine {
        &self.transformation_engine
    }

    pub fn simulate(
        &self,
        plan: &SemanticPlan,
    ) -> Result<SimulationResult, SemanticSimulationError> {
        plan.validate().map_err(SemanticSimulationError::Planning)?;

        let mut states = Vec::with_capacity(plan.steps.len() + 1);
        states.push(plan.start.clone());

        for step in &plan.steps {
            let path = self
                .transformation_engine
                .transformation_path(&step.source, &step.target)
                .map_err(SemanticSimulationError::Transformation)?;
            let distance = path.nodes.len().saturating_sub(1);
            if distance != 1 {
                return Err(SemanticSimulationError::InvalidStep {
                    source: step.source.0.clone(),
                    target: step.target.0.clone(),
                    distance,
                });
            }
            states.push(step.target.clone());
        }

        Ok(SimulationResult {
            initial_state: plan.start.clone(),
            final_state: plan.goal.clone(),
            trace: SimulationTrace { states },
            distance: plan.distance,
            reachable: true,
        })
    }

    pub fn simulate_goal(
        &self,
        current: &SemanticTypeId,
        goal: &SemanticTypeId,
    ) -> Result<SimulationResult, SemanticSimulationError> {
        let plan = self
            .planning_engine
            .shortest_plan(current, goal)
            .map_err(SemanticSimulationError::Planning)?;
        self.simulate(&plan)
    }

    pub fn predict(
        &self,
        current: &SemanticTypeId,
        goal: &SemanticTypeId,
    ) -> Result<SemanticTypeId, SemanticSimulationError> {
        Ok(self.simulate_goal(current, goal)?.final_state)
    }
}
