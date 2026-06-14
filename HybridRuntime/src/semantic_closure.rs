use crate::semantic_constraint::{
    ConstraintKind, ConstraintPolarity, SemanticConstraint, SemanticConstraintError,
    SemanticConstraintId, SemanticConstraintRegistry,
};
use crate::semantic_type::{SemanticTypeError, SemanticTypeId, SemanticTypeRegistry};
use serde::{Deserialize, Serialize};
use std::collections::HashSet;
use std::fmt;

pub const SEMANTIC_CLOSURE_VERSION: &str = "semantic-closure-engine/0.1";
pub const SEMANTIC_CLOSURE_NODE: &str = "SemanticClosure";

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ClosureMetadata {
    pub depth: usize,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SemanticClosure {
    pub root_type: SemanticTypeId,
    pub types: Vec<SemanticTypeId>,
    pub constraints: Vec<SemanticConstraint>,
    pub metadata: ClosureMetadata,
}

impl SemanticClosure {
    pub fn types(&self) -> &[SemanticTypeId] {
        &self.types
    }

    pub fn constraints(&self) -> &[SemanticConstraint] {
        &self.constraints
    }

    pub fn contains_type(&self, type_id: &SemanticTypeId) -> bool {
        self.types.contains(type_id)
    }

    pub fn contains_constraint(&self, predicate: &str) -> bool {
        self.constraints
            .iter()
            .any(|constraint| constraint.predicate == predicate)
    }

    pub fn to_json_pretty(&self) -> Result<String, SemanticClosureError> {
        serde_json::to_string_pretty(self)
            .map_err(|error| SemanticClosureError::Serialization(error.to_string()))
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SemanticClosureConstraintIr {
    pub id: SemanticConstraintId,
    pub target_type: SemanticTypeId,
    pub kind: ConstraintKind,
    pub polarity: ConstraintPolarity,
    pub predicate: String,
}

impl From<&SemanticConstraint> for SemanticClosureConstraintIr {
    fn from(constraint: &SemanticConstraint) -> Self {
        Self {
            id: constraint.id.clone(),
            target_type: constraint.target_type.clone(),
            kind: constraint.kind,
            polarity: constraint.polarity,
            predicate: constraint.predicate.clone(),
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SemanticClosureIrNode {
    pub node_type: String,
    pub version: String,
    pub root_type: SemanticTypeId,
    pub types: Vec<SemanticTypeId>,
    pub constraints: Vec<SemanticClosureConstraintIr>,
    pub metadata: ClosureMetadata,
}

impl From<&SemanticClosure> for SemanticClosureIrNode {
    fn from(closure: &SemanticClosure) -> Self {
        Self {
            node_type: SEMANTIC_CLOSURE_NODE.to_string(),
            version: SEMANTIC_CLOSURE_VERSION.to_string(),
            root_type: closure.root_type.clone(),
            types: closure.types.clone(),
            constraints: closure
                .constraints
                .iter()
                .map(SemanticClosureConstraintIr::from)
                .collect(),
            metadata: closure.metadata.clone(),
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum SemanticClosureError {
    UnknownRootType(String),
    TypeHierarchy(SemanticTypeError),
    ConstraintLookup(SemanticConstraintError),
    DuplicateType(String),
    DuplicateConstraint(String),
    Serialization(String),
}

impl fmt::Display for SemanticClosureError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::UnknownRootType(id) => write!(formatter, "semantic closure root not found: {id}"),
            Self::TypeHierarchy(error) => {
                write!(formatter, "semantic type closure failed: {error}")
            }
            Self::ConstraintLookup(error) => {
                write!(formatter, "semantic constraint closure failed: {error}")
            }
            Self::DuplicateType(id) => {
                write!(formatter, "duplicate type in semantic closure: {id}")
            }
            Self::DuplicateConstraint(id) => {
                write!(formatter, "duplicate constraint in semantic closure: {id}")
            }
            Self::Serialization(message) => {
                write!(
                    formatter,
                    "semantic closure serialization failed: {message}"
                )
            }
        }
    }
}

impl std::error::Error for SemanticClosureError {}

#[derive(Clone, Debug)]
pub struct SemanticClosureEngine {
    type_registry: SemanticTypeRegistry,
    constraint_registry: SemanticConstraintRegistry,
}

impl SemanticClosureEngine {
    pub fn new(
        type_registry: SemanticTypeRegistry,
        constraint_registry: SemanticConstraintRegistry,
    ) -> Self {
        Self {
            type_registry,
            constraint_registry,
        }
    }

    pub fn type_registry(&self) -> &SemanticTypeRegistry {
        &self.type_registry
    }

    pub fn constraint_registry(&self) -> &SemanticConstraintRegistry {
        &self.constraint_registry
    }

    pub fn build_closure(
        &self,
        root: &SemanticTypeId,
    ) -> Result<SemanticClosure, SemanticClosureError> {
        if self.type_registry.get_type(root).is_none() {
            return Err(SemanticClosureError::UnknownRootType(root.0.clone()));
        }

        let types = self
            .type_registry
            .semantic_closure(root)
            .map_err(SemanticClosureError::TypeHierarchy)?;
        validate_unique_types(&types)?;

        let constraints = self
            .constraint_registry
            .get_effective_constraints(&self.type_registry, root)
            .map_err(SemanticClosureError::ConstraintLookup)?;
        let constraints = deduplicate_constraints(constraints);
        validate_unique_constraints(&constraints)?;

        Ok(SemanticClosure {
            root_type: root.clone(),
            metadata: ClosureMetadata {
                depth: types.len().saturating_sub(1),
            },
            types,
            constraints,
        })
    }
}

fn validate_unique_types(types: &[SemanticTypeId]) -> Result<(), SemanticClosureError> {
    let mut seen = HashSet::new();
    for type_id in types {
        if !seen.insert(type_id) {
            return Err(SemanticClosureError::DuplicateType(type_id.0.clone()));
        }
    }
    Ok(())
}

fn deduplicate_constraints(constraints: Vec<SemanticConstraint>) -> Vec<SemanticConstraint> {
    let mut seen = HashSet::new();
    constraints
        .into_iter()
        .filter(|constraint| {
            seen.insert((
                constraint.kind,
                constraint.polarity,
                constraint.predicate.clone(),
            ))
        })
        .collect()
}

fn validate_unique_constraints(
    constraints: &[SemanticConstraint],
) -> Result<(), SemanticClosureError> {
    let mut seen = HashSet::new();
    for constraint in constraints {
        if !seen.insert((
            constraint.kind,
            constraint.polarity,
            constraint.predicate.as_str(),
        )) {
            return Err(SemanticClosureError::DuplicateConstraint(
                constraint.id.0.clone(),
            ));
        }
    }
    Ok(())
}
