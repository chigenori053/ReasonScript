use crate::graph::SemanticPlan;
use crate::semantic_simulation::SimulationResult;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct KnowledgeEvidence {
    pub source_plan: SemanticPlan,
    pub simulation_result: SimulationResult,
}
