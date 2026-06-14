use crate::semantic_type::{SemanticTypeId, SemanticTypeRegistry};
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};
use std::fmt;

pub const SEMANTIC_CONSTRAINT_NODE: &str = "SemanticConstraint";

#[derive(Clone, Debug, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(transparent)]
pub struct SemanticConstraintId(pub String);

impl SemanticConstraintId {
    pub fn new(id: impl Into<String>) -> Result<Self, SemanticConstraintError> {
        let id = id.into();
        validate_constraint_id(&id)?;
        Ok(Self(id))
    }

    pub fn as_str(&self) -> &str {
        &self.0
    }
}

impl From<&str> for SemanticConstraintId {
    fn from(value: &str) -> Self {
        Self(value.to_string())
    }
}

impl From<String> for SemanticConstraintId {
    fn from(value: String) -> Self {
        Self(value)
    }
}

impl fmt::Display for SemanticConstraintId {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str(&self.0)
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum ConstraintKind {
    Property,
    Capability,
    Restriction,
    Requirement,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum ConstraintPolarity {
    Positive,
    Negative,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SemanticConstraint {
    pub id: SemanticConstraintId,
    pub target_type: SemanticTypeId,
    pub kind: ConstraintKind,
    pub polarity: ConstraintPolarity,
    pub predicate: String,
}

impl SemanticConstraint {
    pub fn new(
        id: impl Into<SemanticConstraintId>,
        target_type: impl Into<SemanticTypeId>,
        kind: ConstraintKind,
        polarity: ConstraintPolarity,
        predicate: impl Into<String>,
    ) -> Self {
        Self {
            id: id.into(),
            target_type: target_type.into(),
            kind,
            polarity,
            predicate: predicate.into(),
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SemanticConstraintDeclaration {
    pub node_type: String,
    pub target: SemanticTypeId,
    pub kind: ConstraintKind,
    pub predicate: String,
    pub polarity: ConstraintPolarity,
}

impl SemanticConstraintDeclaration {
    pub fn new(
        target: impl Into<SemanticTypeId>,
        kind: ConstraintKind,
        predicate: impl Into<String>,
        polarity: ConstraintPolarity,
    ) -> Self {
        Self {
            node_type: SEMANTIC_CONSTRAINT_NODE.to_string(),
            target: target.into(),
            kind,
            predicate: predicate.into(),
            polarity,
        }
    }

    pub fn into_constraint(
        self,
        id: impl Into<SemanticConstraintId>,
    ) -> Result<SemanticConstraint, SemanticConstraintError> {
        if self.node_type != SEMANTIC_CONSTRAINT_NODE {
            return Err(SemanticConstraintError::InvalidNodeType(self.node_type));
        }
        Ok(SemanticConstraint {
            id: id.into(),
            target_type: self.target,
            kind: self.kind,
            polarity: self.polarity,
            predicate: self.predicate,
        })
    }
}

impl From<&SemanticConstraint> for SemanticConstraintDeclaration {
    fn from(constraint: &SemanticConstraint) -> Self {
        Self::new(
            constraint.target_type.clone(),
            constraint.kind,
            constraint.predicate.clone(),
            constraint.polarity,
        )
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SemanticConstraintIrNode {
    pub node_type: String,
    pub id: SemanticConstraintId,
    pub target_type: SemanticTypeId,
    pub kind: ConstraintKind,
    pub polarity: ConstraintPolarity,
    pub predicate: String,
}

impl From<&SemanticConstraint> for SemanticConstraintIrNode {
    fn from(constraint: &SemanticConstraint) -> Self {
        Self {
            node_type: SEMANTIC_CONSTRAINT_NODE.to_string(),
            id: constraint.id.clone(),
            target_type: constraint.target_type.clone(),
            kind: constraint.kind,
            polarity: constraint.polarity,
            predicate: constraint.predicate.clone(),
        }
    }
}

impl TryFrom<SemanticConstraintIrNode> for SemanticConstraint {
    type Error = SemanticConstraintError;

    fn try_from(node: SemanticConstraintIrNode) -> Result<Self, Self::Error> {
        if node.node_type != SEMANTIC_CONSTRAINT_NODE {
            return Err(SemanticConstraintError::InvalidNodeType(node.node_type));
        }
        Ok(Self {
            id: node.id,
            target_type: node.target_type,
            kind: node.kind,
            polarity: node.polarity,
            predicate: node.predicate,
        })
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum SemanticConstraintError {
    DuplicateConstraintId(String),
    DuplicateConstraint {
        existing_id: String,
        duplicate_id: String,
    },
    UnknownTargetType(String),
    InvalidPredicate(String),
    InvalidConstraintId(String),
    InvalidNodeType(String),
}

impl fmt::Display for SemanticConstraintError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::DuplicateConstraintId(id) => {
                write!(formatter, "semantic constraint id already exists: {id}")
            }
            Self::DuplicateConstraint {
                existing_id,
                duplicate_id,
            } => write!(
                formatter,
                "semantic constraint {duplicate_id} duplicates {existing_id}"
            ),
            Self::UnknownTargetType(id) => {
                write!(formatter, "semantic constraint target type not found: {id}")
            }
            Self::InvalidPredicate(predicate) => {
                write!(
                    formatter,
                    "invalid semantic constraint predicate: {predicate:?}"
                )
            }
            Self::InvalidConstraintId(id) => {
                write!(formatter, "invalid semantic constraint id: {id:?}")
            }
            Self::InvalidNodeType(node_type) => {
                write!(
                    formatter,
                    "invalid semantic constraint node type: {node_type}"
                )
            }
        }
    }
}

impl std::error::Error for SemanticConstraintError {}

#[derive(Clone, Debug, Default)]
pub struct SemanticConstraintRegistry {
    constraints: HashMap<SemanticTypeId, Vec<SemanticConstraint>>,
    constraint_ids: HashSet<SemanticConstraintId>,
}

impl SemanticConstraintRegistry {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn from_constraints(
        types: &SemanticTypeRegistry,
        constraints: impl IntoIterator<Item = SemanticConstraint>,
    ) -> Result<Self, SemanticConstraintError> {
        let mut registry = Self::new();
        for constraint in constraints {
            registry.add_constraint(types, constraint)?;
        }
        Ok(registry)
    }

    pub fn from_ir_nodes(
        types: &SemanticTypeRegistry,
        nodes: impl IntoIterator<Item = SemanticConstraintIrNode>,
    ) -> Result<Self, SemanticConstraintError> {
        let constraints = nodes
            .into_iter()
            .map(SemanticConstraint::try_from)
            .collect::<Result<Vec<_>, _>>()?;
        Self::from_constraints(types, constraints)
    }

    pub fn add_constraint(
        &mut self,
        types: &SemanticTypeRegistry,
        constraint: SemanticConstraint,
    ) -> Result<(), SemanticConstraintError> {
        validate_constraint_id(constraint.id.as_str())?;
        validate_predicate(&constraint.predicate)?;
        if types.get_type(&constraint.target_type).is_none() {
            return Err(SemanticConstraintError::UnknownTargetType(
                constraint.target_type.0,
            ));
        }
        if self.constraint_ids.contains(&constraint.id) {
            return Err(SemanticConstraintError::DuplicateConstraintId(
                constraint.id.0,
            ));
        }
        if let Some(existing) =
            self.constraints
                .get(&constraint.target_type)
                .and_then(|constraints| {
                    constraints
                        .iter()
                        .find(|existing| same_constraint_content(existing, &constraint))
                })
        {
            return Err(SemanticConstraintError::DuplicateConstraint {
                existing_id: existing.id.0.clone(),
                duplicate_id: constraint.id.0,
            });
        }

        self.constraint_ids.insert(constraint.id.clone());
        self.constraints
            .entry(constraint.target_type.clone())
            .or_default()
            .push(constraint);
        Ok(())
    }

    pub fn get_constraints<'a>(
        &'a self,
        types: &SemanticTypeRegistry,
        target_type: &SemanticTypeId,
    ) -> Result<&'a [SemanticConstraint], SemanticConstraintError> {
        require_type(types, target_type)?;
        Ok(self
            .constraints
            .get(target_type)
            .map(Vec::as_slice)
            .unwrap_or_default())
    }

    pub fn get_effective_constraints(
        &self,
        types: &SemanticTypeRegistry,
        target_type: &SemanticTypeId,
    ) -> Result<Vec<SemanticConstraint>, SemanticConstraintError> {
        require_type(types, target_type)?;
        let type_chain = types
            .semantic_closure(target_type)
            .map_err(|_| SemanticConstraintError::UnknownTargetType(target_type.0.clone()))?;

        Ok(type_chain
            .into_iter()
            .filter_map(|type_id| self.constraints.get(&type_id))
            .flatten()
            .cloned()
            .collect())
    }

    pub fn to_ir_nodes(&self) -> Vec<SemanticConstraintIrNode> {
        let mut constraints = self.constraints.values().flatten().collect::<Vec<_>>();
        constraints.sort_by(|left, right| left.id.cmp(&right.id));
        constraints
            .into_iter()
            .map(SemanticConstraintIrNode::from)
            .collect()
    }
}

fn require_type(
    types: &SemanticTypeRegistry,
    target_type: &SemanticTypeId,
) -> Result<(), SemanticConstraintError> {
    if types.get_type(target_type).is_some() {
        Ok(())
    } else {
        Err(SemanticConstraintError::UnknownTargetType(
            target_type.0.clone(),
        ))
    }
}

fn same_constraint_content(left: &SemanticConstraint, right: &SemanticConstraint) -> bool {
    left.target_type == right.target_type
        && left.kind == right.kind
        && left.polarity == right.polarity
        && left.predicate == right.predicate
}

fn validate_constraint_id(id: &str) -> Result<(), SemanticConstraintError> {
    if id.trim().is_empty() {
        Err(SemanticConstraintError::InvalidConstraintId(id.to_string()))
    } else {
        Ok(())
    }
}

fn validate_predicate(predicate: &str) -> Result<(), SemanticConstraintError> {
    if predicate.trim().is_empty() {
        Err(SemanticConstraintError::InvalidPredicate(
            predicate.to_string(),
        ))
    } else {
        Ok(())
    }
}
