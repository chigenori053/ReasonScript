use crate::semantic_closure::{SemanticClosure, SemanticClosureEngine, SemanticClosureError};
use crate::semantic_constraint::{ConstraintPolarity, SemanticConstraint};
use crate::semantic_type::SemanticTypeId;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fmt;

pub const SEMANTIC_CONTRADICTION_VERSION: &str = "semantic-contradiction-engine/0.1";
pub const SEMANTIC_CONTRADICTION_NODE: &str = "SemanticContradiction";
pub const SEMANTIC_VALIDATION_REPORT_NODE: &str = "SemanticValidationReport";

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum ContradictionKind {
    PolarityConflict,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SemanticContradiction {
    pub predicate: String,
    pub positive_constraints: Vec<SemanticConstraint>,
    pub negative_constraints: Vec<SemanticConstraint>,
    pub kind: ContradictionKind,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum ConsistencyStatus {
    Consistent,
    Contradictory,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SemanticValidationReport {
    pub root_type: SemanticTypeId,
    pub contradictions: Vec<SemanticContradiction>,
    pub status: ConsistencyStatus,
}

impl SemanticValidationReport {
    pub fn is_consistent(&self) -> bool {
        self.status == ConsistencyStatus::Consistent
    }

    pub fn to_json_pretty(&self) -> Result<String, SemanticContradictionError> {
        serde_json::to_string_pretty(self)
            .map_err(|error| SemanticContradictionError::Serialization(error.to_string()))
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SemanticContradictionIrNode {
    pub node_type: String,
    pub predicate: String,
    pub kind: ContradictionKind,
}

impl From<&SemanticContradiction> for SemanticContradictionIrNode {
    fn from(contradiction: &SemanticContradiction) -> Self {
        Self {
            node_type: SEMANTIC_CONTRADICTION_NODE.to_string(),
            predicate: contradiction.predicate.clone(),
            kind: contradiction.kind,
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SemanticValidationReportIrNode {
    pub node_type: String,
    pub version: String,
    pub root_type: SemanticTypeId,
    pub status: ConsistencyStatus,
    pub contradictions: Vec<SemanticContradictionIrNode>,
}

impl From<&SemanticValidationReport> for SemanticValidationReportIrNode {
    fn from(report: &SemanticValidationReport) -> Self {
        Self {
            node_type: SEMANTIC_VALIDATION_REPORT_NODE.to_string(),
            version: SEMANTIC_CONTRADICTION_VERSION.to_string(),
            root_type: report.root_type.clone(),
            status: report.status,
            contradictions: report
                .contradictions
                .iter()
                .map(SemanticContradictionIrNode::from)
                .collect(),
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum SemanticContradictionError {
    Closure(SemanticClosureError),
    Serialization(String),
}

impl fmt::Display for SemanticContradictionError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Closure(error) => {
                write!(
                    formatter,
                    "semantic contradiction validation failed: {error}"
                )
            }
            Self::Serialization(message) => {
                write!(
                    formatter,
                    "semantic contradiction serialization failed: {message}"
                )
            }
        }
    }
}

impl std::error::Error for SemanticContradictionError {}

#[derive(Clone, Debug)]
pub struct SemanticContradictionEngine {
    closure_engine: SemanticClosureEngine,
}

impl SemanticContradictionEngine {
    pub fn new(closure_engine: SemanticClosureEngine) -> Self {
        Self { closure_engine }
    }

    pub fn closure_engine(&self) -> &SemanticClosureEngine {
        &self.closure_engine
    }

    pub fn validate(
        &self,
        root: &SemanticTypeId,
    ) -> Result<SemanticValidationReport, SemanticContradictionError> {
        let closure = self
            .closure_engine
            .build_closure(root)
            .map_err(SemanticContradictionError::Closure)?;
        let contradictions = self.find_contradictions(&closure);
        let status = if contradictions.is_empty() {
            ConsistencyStatus::Consistent
        } else {
            ConsistencyStatus::Contradictory
        };

        Ok(SemanticValidationReport {
            root_type: root.clone(),
            contradictions,
            status,
        })
    }

    pub fn find_contradictions(&self, closure: &SemanticClosure) -> Vec<SemanticContradiction> {
        let mut groups = Vec::<PredicateConstraints>::new();
        let mut positions = HashMap::<&str, usize>::new();

        for constraint in &closure.constraints {
            let position = match positions.get(constraint.predicate.as_str()) {
                Some(position) => *position,
                None => {
                    let position = groups.len();
                    positions.insert(constraint.predicate.as_str(), position);
                    groups.push(PredicateConstraints {
                        predicate: constraint.predicate.clone(),
                        positive: Vec::new(),
                        negative: Vec::new(),
                    });
                    position
                }
            };
            match constraint.polarity {
                ConstraintPolarity::Positive => {
                    groups[position].positive.push(constraint.clone());
                }
                ConstraintPolarity::Negative => {
                    groups[position].negative.push(constraint.clone());
                }
            }
        }

        groups
            .into_iter()
            .filter(|group| !group.positive.is_empty() && !group.negative.is_empty())
            .map(|group| SemanticContradiction {
                predicate: group.predicate,
                positive_constraints: group.positive,
                negative_constraints: group.negative,
                kind: ContradictionKind::PolarityConflict,
            })
            .collect()
    }

    pub fn is_consistent(&self, closure: &SemanticClosure) -> bool {
        self.find_contradictions(closure).is_empty()
    }
}

struct PredicateConstraints {
    predicate: String,
    positive: Vec<SemanticConstraint>,
    negative: Vec<SemanticConstraint>,
}
