use crate::semantic_type::{SemanticTypeError, SemanticTypeId, SemanticTypeRegistry};
use serde::{Deserialize, Serialize};
use std::fmt;

pub const SEMANTIC_TRANSFORMATION_VERSION: &str = "semantic-transformation-engine/0.1";
pub const TRANSFORMATION_PATH_NODE: &str = "TransformationPath";
pub const TRANSFORMATION_RESULT_NODE: &str = "TransformationResult";

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum TransformationKind {
    Generalization,
    Specialization,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TransformationPath {
    pub nodes: Vec<SemanticTypeId>,
}

impl TransformationPath {
    pub fn to_json_pretty(&self) -> Result<String, SemanticTransformationError> {
        serde_json::to_string_pretty(self)
            .map_err(|error| SemanticTransformationError::Serialization(error.to_string()))
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TransformationResult {
    pub source: SemanticTypeId,
    pub target: SemanticTypeId,
    pub kind: TransformationKind,
    pub path: TransformationPath,
    pub distance: usize,
}

impl TransformationResult {
    pub fn to_json_pretty(&self) -> Result<String, SemanticTransformationError> {
        serde_json::to_string_pretty(self)
            .map_err(|error| SemanticTransformationError::Serialization(error.to_string()))
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TransformationPathIrNode {
    pub node_type: String,
    pub nodes: Vec<SemanticTypeId>,
}

impl From<&TransformationPath> for TransformationPathIrNode {
    fn from(path: &TransformationPath) -> Self {
        Self {
            node_type: TRANSFORMATION_PATH_NODE.to_string(),
            nodes: path.nodes.clone(),
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TransformationResultIrNode {
    pub node_type: String,
    pub source: SemanticTypeId,
    pub target: SemanticTypeId,
    pub kind: TransformationKind,
    pub distance: usize,
}

impl From<&TransformationResult> for TransformationResultIrNode {
    fn from(result: &TransformationResult) -> Self {
        Self {
            node_type: TRANSFORMATION_RESULT_NODE.to_string(),
            source: result.source.clone(),
            target: result.target.clone(),
            kind: result.kind,
            distance: result.distance,
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum SemanticTransformationError {
    TypeHierarchy(SemanticTypeError),
    InvalidGeneralizationLevel {
        source: String,
        levels: usize,
        maximum: usize,
    },
    InvalidDirection {
        source: String,
        target: String,
        kind: TransformationKind,
    },
    NoTransformationPath {
        source: String,
        target: String,
    },
    Serialization(String),
}

impl fmt::Display for SemanticTransformationError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::TypeHierarchy(error) => {
                write!(
                    formatter,
                    "semantic transformation hierarchy failed: {error}"
                )
            }
            Self::InvalidGeneralizationLevel {
                source,
                levels,
                maximum,
            } => write!(
                formatter,
                "cannot generalize {source} by {levels} levels; maximum is {maximum}"
            ),
            Self::InvalidDirection {
                source,
                target,
                kind,
            } => write!(
                formatter,
                "invalid {kind:?} direction from {source} to {target}"
            ),
            Self::NoTransformationPath { source, target } => {
                write!(
                    formatter,
                    "no semantic transformation path from {source} to {target}"
                )
            }
            Self::Serialization(message) => {
                write!(
                    formatter,
                    "semantic transformation serialization failed: {message}"
                )
            }
        }
    }
}

impl std::error::Error for SemanticTransformationError {}

impl From<SemanticTypeError> for SemanticTransformationError {
    fn from(error: SemanticTypeError) -> Self {
        Self::TypeHierarchy(error)
    }
}

#[derive(Clone, Debug)]
pub struct SemanticTransformationEngine {
    type_registry: SemanticTypeRegistry,
}

impl SemanticTransformationEngine {
    pub fn new(type_registry: SemanticTypeRegistry) -> Self {
        Self { type_registry }
    }

    pub fn type_registry(&self) -> &SemanticTypeRegistry {
        &self.type_registry
    }

    pub fn generalize(
        &self,
        source: &SemanticTypeId,
        levels: usize,
    ) -> Result<TransformationResult, SemanticTransformationError> {
        let nodes = self.type_registry.semantic_closure(source)?;
        let maximum = nodes.len().saturating_sub(1);
        if levels > maximum {
            return Err(SemanticTransformationError::InvalidGeneralizationLevel {
                source: source.0.clone(),
                levels,
                maximum,
            });
        }

        let path = TransformationPath {
            nodes: nodes[..=levels].to_vec(),
        };
        let target = path.nodes[levels].clone();
        Ok(build_result(
            source,
            &target,
            TransformationKind::Generalization,
            path,
        ))
    }

    pub fn generalize_to(
        &self,
        source: &SemanticTypeId,
        target: &SemanticTypeId,
    ) -> Result<TransformationResult, SemanticTransformationError> {
        self.require_types(source, target)?;
        let nodes = self.type_registry.semantic_closure(source)?;
        let Some(position) = nodes.iter().position(|node| node == target) else {
            return Err(SemanticTransformationError::InvalidDirection {
                source: source.0.clone(),
                target: target.0.clone(),
                kind: TransformationKind::Generalization,
            });
        };
        let path = TransformationPath {
            nodes: nodes[..=position].to_vec(),
        };

        Ok(build_result(
            source,
            target,
            TransformationKind::Generalization,
            path,
        ))
    }

    pub fn specialize(
        &self,
        source: &SemanticTypeId,
    ) -> Result<Vec<TransformationResult>, SemanticTransformationError> {
        self.type_registry
            .get_descendants(source)?
            .into_iter()
            .map(|target| self.specialize_to(source, &target))
            .collect()
    }

    pub fn specialize_to(
        &self,
        source: &SemanticTypeId,
        target: &SemanticTypeId,
    ) -> Result<TransformationResult, SemanticTransformationError> {
        self.require_types(source, target)?;
        let target_closure = self.type_registry.semantic_closure(target)?;
        let Some(position) = target_closure.iter().position(|node| node == source) else {
            return Err(SemanticTransformationError::InvalidDirection {
                source: source.0.clone(),
                target: target.0.clone(),
                kind: TransformationKind::Specialization,
            });
        };
        let mut nodes = target_closure[..=position].to_vec();
        nodes.reverse();
        let path = TransformationPath { nodes };

        Ok(build_result(
            source,
            target,
            TransformationKind::Specialization,
            path,
        ))
    }

    pub fn transformation_path(
        &self,
        source: &SemanticTypeId,
        target: &SemanticTypeId,
    ) -> Result<TransformationPath, SemanticTransformationError> {
        self.require_types(source, target)?;

        if source == target {
            return Ok(TransformationPath {
                nodes: vec![source.clone()],
            });
        }
        if let Ok(result) = self.generalize_to(source, target) {
            return Ok(result.path);
        }
        if let Ok(result) = self.specialize_to(source, target) {
            return Ok(result.path);
        }

        Err(SemanticTransformationError::NoTransformationPath {
            source: source.0.clone(),
            target: target.0.clone(),
        })
    }

    fn require_types(
        &self,
        source: &SemanticTypeId,
        target: &SemanticTypeId,
    ) -> Result<(), SemanticTransformationError> {
        self.type_registry.semantic_closure(source)?;
        self.type_registry.semantic_closure(target)?;
        Ok(())
    }
}

fn build_result(
    source: &SemanticTypeId,
    target: &SemanticTypeId,
    kind: TransformationKind,
    path: TransformationPath,
) -> TransformationResult {
    TransformationResult {
        source: source.clone(),
        target: target.clone(),
        kind,
        distance: path.nodes.len().saturating_sub(1),
        path,
    }
}
