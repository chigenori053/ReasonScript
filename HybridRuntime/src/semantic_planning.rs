use crate::semantic_transformation::{
    SemanticTransformationEngine, SemanticTransformationError, TransformationPath,
};
use crate::semantic_type::SemanticTypeId;
use serde::{Deserialize, Serialize};
use std::fmt;

pub const SEMANTIC_PLANNING_VERSION: &str = "semantic-planning-engine/0.1";
pub const SEMANTIC_PLAN_NODE: &str = "SemanticPlan";
pub const PLANNING_RESULT_NODE: &str = "PlanningResult";

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PlanningGoal {
    pub target: SemanticTypeId,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PlanningState {
    pub current: SemanticTypeId,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PlanStep {
    pub source: SemanticTypeId,
    pub target: SemanticTypeId,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SemanticPlan {
    pub start: SemanticTypeId,
    pub goal: SemanticTypeId,
    pub steps: Vec<PlanStep>,
    pub distance: usize,
}

impl SemanticPlan {
    pub fn validate(&self) -> Result<(), SemanticPlanningError> {
        if self.distance != self.steps.len() {
            return Err(SemanticPlanningError::InvalidPlan {
                reason: format!(
                    "distance {} does not match step count {}",
                    self.distance,
                    self.steps.len()
                ),
            });
        }

        if self.steps.is_empty() {
            if self.start != self.goal {
                return Err(SemanticPlanningError::InvalidPlan {
                    reason: "a zero-step plan must have identical start and goal".to_string(),
                });
            }
            return Ok(());
        }

        if self.steps.first().map(|step| &step.source) != Some(&self.start) {
            return Err(SemanticPlanningError::InvalidPlan {
                reason: "first step source does not match plan start".to_string(),
            });
        }
        if self.steps.last().map(|step| &step.target) != Some(&self.goal) {
            return Err(SemanticPlanningError::InvalidPlan {
                reason: "last step target does not match plan goal".to_string(),
            });
        }
        if self
            .steps
            .windows(2)
            .any(|steps| steps[0].target != steps[1].source)
        {
            return Err(SemanticPlanningError::InvalidPlan {
                reason: "plan steps are not contiguous".to_string(),
            });
        }

        Ok(())
    }

    pub fn to_json_pretty(&self) -> Result<String, SemanticPlanningError> {
        serde_json::to_string_pretty(self)
            .map_err(|error| SemanticPlanningError::Serialization(error.to_string()))
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PlanningResult {
    pub goal: PlanningGoal,
    pub plans: Vec<SemanticPlan>,
}

impl PlanningResult {
    pub fn to_json_pretty(&self) -> Result<String, SemanticPlanningError> {
        serde_json::to_string_pretty(self)
            .map_err(|error| SemanticPlanningError::Serialization(error.to_string()))
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SemanticPlanIrNode {
    pub node_type: String,
    pub start: SemanticTypeId,
    pub goal: SemanticTypeId,
    pub distance: usize,
}

impl From<&SemanticPlan> for SemanticPlanIrNode {
    fn from(plan: &SemanticPlan) -> Self {
        Self {
            node_type: SEMANTIC_PLAN_NODE.to_string(),
            start: plan.start.clone(),
            goal: plan.goal.clone(),
            distance: plan.distance,
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PlanningResultIrNode {
    pub node_type: String,
    pub goal: SemanticTypeId,
    pub plans: Vec<SemanticPlanIrNode>,
}

impl From<&PlanningResult> for PlanningResultIrNode {
    fn from(result: &PlanningResult) -> Self {
        Self {
            node_type: PLANNING_RESULT_NODE.to_string(),
            goal: result.goal.target.clone(),
            plans: result.plans.iter().map(SemanticPlanIrNode::from).collect(),
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum SemanticPlanningError {
    Transformation(SemanticTransformationError),
    InvalidPlan { reason: String },
    Unreachable { current: String, goal: String },
    Serialization(String),
}

impl fmt::Display for SemanticPlanningError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Transformation(error) => {
                write!(
                    formatter,
                    "semantic planning transformation failed: {error}"
                )
            }
            Self::InvalidPlan { reason } => write!(formatter, "invalid semantic plan: {reason}"),
            Self::Unreachable { current, goal } => {
                write!(
                    formatter,
                    "semantic goal {goal} is unreachable from {current}"
                )
            }
            Self::Serialization(message) => {
                write!(
                    formatter,
                    "semantic planning serialization failed: {message}"
                )
            }
        }
    }
}

impl std::error::Error for SemanticPlanningError {}

impl From<SemanticTransformationError> for SemanticPlanningError {
    fn from(error: SemanticTransformationError) -> Self {
        Self::Transformation(error)
    }
}

#[derive(Clone, Debug)]
pub struct SemanticPlanningEngine {
    transformation_engine: SemanticTransformationEngine,
}

impl SemanticPlanningEngine {
    pub fn new(transformation_engine: SemanticTransformationEngine) -> Self {
        Self {
            transformation_engine,
        }
    }

    pub fn transformation_engine(&self) -> &SemanticTransformationEngine {
        &self.transformation_engine
    }

    pub fn plan(
        &self,
        current: &SemanticTypeId,
        goal: &SemanticTypeId,
    ) -> Result<PlanningResult, SemanticPlanningError> {
        let path = match self
            .transformation_engine
            .transformation_path(current, goal)
        {
            Ok(path) => path,
            Err(SemanticTransformationError::NoTransformationPath { .. }) => {
                return Ok(PlanningResult {
                    goal: PlanningGoal {
                        target: goal.clone(),
                    },
                    plans: Vec::new(),
                });
            }
            Err(error) => return Err(error.into()),
        };
        let semantic_plan = build_plan(current, goal, &path)?;

        Ok(PlanningResult {
            goal: PlanningGoal {
                target: goal.clone(),
            },
            plans: vec![semantic_plan],
        })
    }

    pub fn shortest_plan(
        &self,
        current: &SemanticTypeId,
        goal: &SemanticTypeId,
    ) -> Result<SemanticPlan, SemanticPlanningError> {
        self.plan(current, goal)?
            .plans
            .into_iter()
            .min_by(|left, right| {
                left.distance
                    .cmp(&right.distance)
                    .then_with(|| left.goal.cmp(&right.goal))
            })
            .ok_or_else(|| SemanticPlanningError::Unreachable {
                current: current.0.clone(),
                goal: goal.0.clone(),
            })
    }

    pub fn reachable(&self, current: &SemanticTypeId, goal: &SemanticTypeId) -> bool {
        self.transformation_engine
            .transformation_path(current, goal)
            .is_ok()
    }
}

fn build_plan(
    current: &SemanticTypeId,
    goal: &SemanticTypeId,
    path: &TransformationPath,
) -> Result<SemanticPlan, SemanticPlanningError> {
    let steps = path
        .nodes
        .windows(2)
        .map(|nodes| PlanStep {
            source: nodes[0].clone(),
            target: nodes[1].clone(),
        })
        .collect::<Vec<_>>();
    let plan = SemanticPlan {
        start: current.clone(),
        goal: goal.clone(),
        distance: steps.len(),
        steps,
    };
    plan.validate()?;
    Ok(plan)
}
