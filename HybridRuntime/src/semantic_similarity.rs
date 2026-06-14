use crate::semantic_closure::{SemanticClosure, SemanticClosureEngine, SemanticClosureError};
use crate::semantic_type::SemanticTypeId;
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};
use std::fmt;

pub const SEMANTIC_SIMILARITY_VERSION: &str = "semantic-similarity-engine/0.1";
pub const SIMILARITY_RESULT_NODE: &str = "SimilarityResult";
pub const SIMILARITY_REPORT_NODE: &str = "SimilarityReport";

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SimilarityResult {
    pub left: SemanticTypeId,
    pub right: SemanticTypeId,
    pub similarity: f64,
    pub type_similarity: f64,
    pub constraint_similarity: f64,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SimilarityReport {
    pub root_type: SemanticTypeId,
    pub neighbors: Vec<SimilarityResult>,
}

impl SimilarityReport {
    pub fn to_json_pretty(&self) -> Result<String, SemanticSimilarityError> {
        serde_json::to_string_pretty(self)
            .map_err(|error| SemanticSimilarityError::Serialization(error.to_string()))
    }
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SimilarityResultIrNode {
    pub node_type: String,
    pub left: SemanticTypeId,
    pub right: SemanticTypeId,
    pub similarity: f64,
    pub type_similarity: f64,
    pub constraint_similarity: f64,
}

impl From<&SimilarityResult> for SimilarityResultIrNode {
    fn from(result: &SimilarityResult) -> Self {
        Self {
            node_type: SIMILARITY_RESULT_NODE.to_string(),
            left: result.left.clone(),
            right: result.right.clone(),
            similarity: result.similarity,
            type_similarity: result.type_similarity,
            constraint_similarity: result.constraint_similarity,
        }
    }
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SimilarityReportIrNode {
    pub node_type: String,
    pub version: String,
    pub root_type: SemanticTypeId,
    pub neighbors: Vec<SimilarityResultIrNode>,
}

impl From<&SimilarityReport> for SimilarityReportIrNode {
    fn from(report: &SimilarityReport) -> Self {
        Self {
            node_type: SIMILARITY_REPORT_NODE.to_string(),
            version: SEMANTIC_SIMILARITY_VERSION.to_string(),
            root_type: report.root_type.clone(),
            neighbors: report
                .neighbors
                .iter()
                .map(SimilarityResultIrNode::from)
                .collect(),
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum SemanticSimilarityError {
    Closure(SemanticClosureError),
    NoCommonAncestor { left: String, right: String },
    Serialization(String),
}

impl fmt::Display for SemanticSimilarityError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Closure(error) => {
                write!(formatter, "semantic similarity closure failed: {error}")
            }
            Self::NoCommonAncestor { left, right } => {
                write!(
                    formatter,
                    "no common semantic ancestor for {left} and {right}"
                )
            }
            Self::Serialization(message) => {
                write!(
                    formatter,
                    "semantic similarity serialization failed: {message}"
                )
            }
        }
    }
}

impl std::error::Error for SemanticSimilarityError {}

#[derive(Clone, Debug)]
pub struct SemanticSimilarityEngine {
    closure_engine: SemanticClosureEngine,
}

impl SemanticSimilarityEngine {
    pub fn new(closure_engine: SemanticClosureEngine) -> Self {
        Self { closure_engine }
    }

    pub fn closure_engine(&self) -> &SemanticClosureEngine {
        &self.closure_engine
    }

    pub fn distance(
        &self,
        left: &SemanticTypeId,
        right: &SemanticTypeId,
    ) -> Result<usize, SemanticSimilarityError> {
        let left_types = self
            .closure_engine
            .type_registry()
            .semantic_closure(left)
            .map_err(|error| {
                SemanticSimilarityError::Closure(SemanticClosureError::TypeHierarchy(error))
            })?;
        let right_types = self
            .closure_engine
            .type_registry()
            .semantic_closure(right)
            .map_err(|error| {
                SemanticSimilarityError::Closure(SemanticClosureError::TypeHierarchy(error))
            })?;
        let right_positions = right_types
            .iter()
            .enumerate()
            .map(|(position, type_id)| (type_id, position))
            .collect::<HashMap<_, _>>();

        left_types
            .iter()
            .enumerate()
            .filter_map(|(left_position, type_id)| {
                right_positions
                    .get(type_id)
                    .map(|right_position| left_position + *right_position)
            })
            .min()
            .ok_or_else(|| SemanticSimilarityError::NoCommonAncestor {
                left: left.0.clone(),
                right: right.0.clone(),
            })
    }

    pub fn similarity(
        &self,
        left: &SemanticTypeId,
        right: &SemanticTypeId,
    ) -> Result<SimilarityResult, SemanticSimilarityError> {
        let left_closure = self
            .closure_engine
            .build_closure(left)
            .map_err(SemanticSimilarityError::Closure)?;
        let right_closure = self
            .closure_engine
            .build_closure(right)
            .map_err(SemanticSimilarityError::Closure)?;
        let distance = self.distance(left, right)?;
        let type_similarity = 1.0 / (1.0 + distance as f64);
        let constraint_similarity = constraint_similarity(&left_closure, &right_closure);
        let similarity = 0.5 * type_similarity + 0.5 * constraint_similarity;

        Ok(SimilarityResult {
            left: left.clone(),
            right: right.clone(),
            similarity,
            type_similarity,
            constraint_similarity,
        })
    }

    pub fn nearest_neighbors(
        &self,
        root: &SemanticTypeId,
        limit: usize,
    ) -> Result<SimilarityReport, SemanticSimilarityError> {
        self.closure_engine
            .build_closure(root)
            .map_err(SemanticSimilarityError::Closure)?;

        let mut neighbors = self
            .closure_engine
            .type_registry()
            .type_ids()
            .into_iter()
            .filter(|candidate| candidate != root)
            .map(|candidate| self.similarity(root, &candidate))
            .collect::<Result<Vec<_>, _>>()?;

        neighbors.sort_by(|left, right| {
            right
                .similarity
                .total_cmp(&left.similarity)
                .then_with(|| left.right.cmp(&right.right))
        });
        neighbors.truncate(limit);

        Ok(SimilarityReport {
            root_type: root.clone(),
            neighbors,
        })
    }
}

fn constraint_similarity(left: &SemanticClosure, right: &SemanticClosure) -> f64 {
    let left_predicates = left
        .constraints
        .iter()
        .map(|constraint| constraint.predicate.as_str())
        .collect::<HashSet<_>>();
    let right_predicates = right
        .constraints
        .iter()
        .map(|constraint| constraint.predicate.as_str())
        .collect::<HashSet<_>>();
    let union_size = left_predicates.union(&right_predicates).count();

    if union_size == 0 {
        1.0
    } else {
        left_predicates.intersection(&right_predicates).count() as f64 / union_size as f64
    }
}
