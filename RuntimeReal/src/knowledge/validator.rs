use crate::core::types::RelationType;
use crate::core::StructuralConstraintValidator;
use crate::semantic_simulation::SimulationResult;
use std::fmt;

#[derive(Debug, Clone, PartialEq)]
pub enum KnowledgeError {
    SimulationFailed,
    EmptyTrajectory,
    InvalidEvidence(String),
    UnsupportedRelation(RelationType),
    MixedRelations {
        expected: RelationType,
        found: RelationType,
    },
    ScvViolation {
        relation: RelationType,
    },
    InvalidConfidence(f64),
    Serialization(String),
}

impl fmt::Display for KnowledgeError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::SimulationFailed => {
                write!(
                    formatter,
                    "knowledge cannot emerge from a failed simulation"
                )
            }
            Self::EmptyTrajectory => {
                write!(
                    formatter,
                    "knowledge requires a non-empty reasoning trajectory"
                )
            }
            Self::InvalidEvidence(message) => {
                write!(formatter, "invalid knowledge evidence: {message}")
            }
            Self::UnsupportedRelation(relation) => {
                write!(formatter, "relation {relation:?} is not supported by KEV-1")
            }
            Self::MixedRelations { expected, found } => write!(
                formatter,
                "knowledge trajectory mixes relations: expected {expected:?}, found {found:?}"
            ),
            Self::ScvViolation { relation } => {
                write!(formatter, "emergent relation {relation:?} violates SCV-1")
            }
            Self::InvalidConfidence(confidence) => {
                write!(formatter, "invalid knowledge confidence {confidence}")
            }
            Self::Serialization(message) => {
                write!(formatter, "knowledge serialization failed: {message}")
            }
        }
    }
}

impl std::error::Error for KnowledgeError {}

#[derive(Debug, Clone, Default)]
pub struct KnowledgeValidator;

impl KnowledgeValidator {
    pub fn validate(&self, result: &SimulationResult) -> Result<(), KnowledgeError> {
        if !result.success {
            return Err(KnowledgeError::SimulationFailed);
        }
        if result.distance == 0 {
            return Err(KnowledgeError::EmptyTrajectory);
        }
        if !result.confidence.is_finite() || !(0.0..=1.0).contains(&result.confidence) {
            return Err(KnowledgeError::InvalidConfidence(result.confidence));
        }
        if result.path.len() != result.distance + 1 {
            return Err(KnowledgeError::InvalidEvidence(
                "path length does not match distance".to_string(),
            ));
        }
        if result.trace.states != result.path {
            return Err(KnowledgeError::InvalidEvidence(
                "trace states do not match the simulation path".to_string(),
            ));
        }
        if result.trace.steps.len() != result.distance {
            return Err(KnowledgeError::InvalidEvidence(
                "trace step count does not match distance".to_string(),
            ));
        }
        if result.source_plan.start != result.path[0]
            || result.source_plan.goal != result.path[result.path.len() - 1]
        {
            return Err(KnowledgeError::InvalidEvidence(
                "source plan does not match path endpoints".to_string(),
            ));
        }
        if result
            .source_plan
            .constraints
            .avoid_nodes
            .iter()
            .any(|node| result.path.contains(node))
        {
            return Err(KnowledgeError::InvalidEvidence(
                "simulation path violates source plan avoidance constraints".to_string(),
            ));
        }
        if result
            .source_plan
            .constraints
            .max_distance
            .is_some_and(|maximum| result.distance > maximum)
        {
            return Err(KnowledgeError::InvalidEvidence(
                "simulation distance exceeds the source plan maximum".to_string(),
            ));
        }
        if result.predicted_states != result.path[1..] {
            return Err(KnowledgeError::InvalidEvidence(
                "predicted states do not match the selected trajectory".to_string(),
            ));
        }

        let relation = result.trace.steps[0].relation;
        if !is_supported(relation) {
            return Err(KnowledgeError::UnsupportedRelation(relation));
        }

        let mut cost = 0.0;
        let mut confidence = 1.0;
        for (index, step) in result.trace.steps.iter().enumerate() {
            if step.source != result.path[index] || step.target != result.path[index + 1] {
                return Err(KnowledgeError::InvalidEvidence(
                    "trace transition does not match path".to_string(),
                ));
            }
            if step.relation != relation {
                return Err(KnowledgeError::MixedRelations {
                    expected: relation,
                    found: step.relation,
                });
            }
            if !StructuralConstraintValidator::is_compatible(
                step.source_type,
                step.relation,
                step.target_type,
            ) {
                return Err(KnowledgeError::ScvViolation {
                    relation: step.relation,
                });
            }
            if !step.cost.is_finite() || step.cost < 0.0 {
                return Err(KnowledgeError::InvalidEvidence(
                    "trace contains an invalid edge cost".to_string(),
                ));
            }
            if !step.confidence.is_finite() || !(0.0..=1.0).contains(&step.confidence) {
                return Err(KnowledgeError::InvalidEvidence(
                    "trace contains an invalid edge confidence".to_string(),
                ));
            }
            cost = normalize_metric(cost + step.cost);
            confidence = normalize_metric(confidence * step.confidence);
        }
        if cost != result.cost || confidence != result.confidence {
            return Err(KnowledgeError::InvalidEvidence(
                "simulation metrics do not match the trace".to_string(),
            ));
        }

        let source_type = result.trace.steps[0].source_type;
        let target_type = result.trace.steps[result.trace.steps.len() - 1].target_type;
        if !StructuralConstraintValidator::is_compatible(source_type, relation, target_type) {
            return Err(KnowledgeError::ScvViolation { relation });
        }

        Ok(())
    }
}

fn is_supported(relation: RelationType) -> bool {
    matches!(
        relation,
        RelationType::IsA | RelationType::PartOf | RelationType::Cause
    )
}

fn normalize_metric(value: f64) -> f64 {
    const SCALE: f64 = 1_000_000_000_000.0;
    (value * SCALE).round() / SCALE
}
