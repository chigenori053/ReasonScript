use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet, VecDeque};
use std::fmt;

pub const SEMANTIC_TYPE_NODE: &str = "SemanticType";
pub const SEMANTIC_TYPE_DECLARATION_NODE: &str = "SemanticTypeDeclaration";
pub const SEMANTIC_RELATION_NODE: &str = "Relation";
pub const IS_A_RELATION: &str = "IsA";

#[derive(Clone, Debug, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(transparent)]
pub struct SemanticTypeId(pub String);

impl SemanticTypeId {
    pub fn new(id: impl Into<String>) -> Result<Self, SemanticTypeError> {
        let id = id.into();
        validate_type_id(&id)?;
        Ok(Self(id))
    }

    pub fn as_str(&self) -> &str {
        &self.0
    }
}

impl From<&str> for SemanticTypeId {
    fn from(value: &str) -> Self {
        Self(value.to_string())
    }
}

impl From<String> for SemanticTypeId {
    fn from(value: String) -> Self {
        Self(value)
    }
}

impl fmt::Display for SemanticTypeId {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str(&self.0)
    }
}

#[derive(Clone, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SemanticTypeMetadata {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub description: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub declared_in: Option<String>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SemanticType {
    pub id: SemanticTypeId,
    pub name: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub parent: Option<SemanticTypeId>,
    #[serde(default)]
    pub metadata: SemanticTypeMetadata,
}

impl SemanticType {
    pub fn root(id: impl Into<SemanticTypeId>) -> Self {
        let id = id.into();
        Self {
            name: id.0.clone(),
            id,
            parent: None,
            metadata: SemanticTypeMetadata::default(),
        }
    }

    pub fn child(id: impl Into<SemanticTypeId>, parent: impl Into<SemanticTypeId>) -> Self {
        let id = id.into();
        Self {
            name: id.0.clone(),
            id,
            parent: Some(parent.into()),
            metadata: SemanticTypeMetadata::default(),
        }
    }

    pub fn with_metadata(mut self, metadata: SemanticTypeMetadata) -> Self {
        self.metadata = metadata;
        self
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SemanticTypeDeclaration {
    pub node_type: String,
    pub name: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub parent: Option<String>,
    #[serde(default)]
    pub metadata: SemanticTypeMetadata,
}

impl SemanticTypeDeclaration {
    pub fn new(name: impl Into<String>, parent: Option<impl Into<String>>) -> Self {
        Self {
            node_type: SEMANTIC_TYPE_DECLARATION_NODE.to_string(),
            name: name.into(),
            parent: parent.map(Into::into),
            metadata: SemanticTypeMetadata::default(),
        }
    }
}

impl TryFrom<SemanticTypeDeclaration> for SemanticType {
    type Error = SemanticTypeError;

    fn try_from(declaration: SemanticTypeDeclaration) -> Result<Self, Self::Error> {
        if declaration.node_type != SEMANTIC_TYPE_DECLARATION_NODE {
            return Err(SemanticTypeError::InvalidNodeType(declaration.node_type));
        }
        let id = SemanticTypeId::new(declaration.name)?;
        Ok(Self {
            name: id.0.clone(),
            id,
            parent: declaration.parent.map(SemanticTypeId),
            metadata: declaration.metadata,
        })
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SemanticTypeIrNode {
    pub node_type: String,
    pub id: SemanticTypeId,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub parent: Option<SemanticTypeId>,
    #[serde(default)]
    pub metadata: SemanticTypeMetadata,
}

impl From<&SemanticType> for SemanticTypeIrNode {
    fn from(type_def: &SemanticType) -> Self {
        Self {
            node_type: SEMANTIC_TYPE_NODE.to_string(),
            id: type_def.id.clone(),
            parent: type_def.parent.clone(),
            metadata: type_def.metadata.clone(),
        }
    }
}

impl TryFrom<SemanticTypeIrNode> for SemanticType {
    type Error = SemanticTypeError;

    fn try_from(node: SemanticTypeIrNode) -> Result<Self, Self::Error> {
        if node.node_type != SEMANTIC_TYPE_NODE {
            return Err(SemanticTypeError::InvalidNodeType(node.node_type));
        }
        validate_type_id(node.id.as_str())?;
        Ok(Self {
            name: node.id.0.clone(),
            id: node.id,
            parent: node.parent,
            metadata: node.metadata,
        })
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SemanticRelation {
    pub node_type: String,
    pub relation_type: String,
    pub source: SemanticTypeId,
    pub target: SemanticTypeId,
}

impl SemanticRelation {
    fn is_a(source: SemanticTypeId, target: SemanticTypeId) -> Self {
        Self {
            node_type: SEMANTIC_RELATION_NODE.to_string(),
            relation_type: IS_A_RELATION.to_string(),
            source,
            target,
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum SemanticTypeError {
    DuplicateType(String),
    UnknownParent(String),
    TypeNotFound(String),
    SelfInheritance(String),
    CircularInheritance(Vec<String>),
    InvalidTypeId(String),
    InvalidNodeType(String),
}

impl fmt::Display for SemanticTypeError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::DuplicateType(id) => write!(formatter, "semantic type already exists: {id}"),
            Self::UnknownParent(id) => write!(formatter, "unknown semantic parent: {id}"),
            Self::TypeNotFound(id) => write!(formatter, "semantic type not found: {id}"),
            Self::SelfInheritance(id) => {
                write!(formatter, "semantic type cannot inherit from itself: {id}")
            }
            Self::CircularInheritance(path) => {
                write!(
                    formatter,
                    "circular semantic inheritance: {}",
                    path.join(" -> ")
                )
            }
            Self::InvalidTypeId(id) => write!(formatter, "invalid semantic type id: {id:?}"),
            Self::InvalidNodeType(node_type) => {
                write!(formatter, "invalid semantic node type: {node_type}")
            }
        }
    }
}

impl std::error::Error for SemanticTypeError {}

#[derive(Clone, Debug, Default)]
pub struct SemanticTypeRegistry {
    types: HashMap<SemanticTypeId, SemanticType>,
    registration_order: Vec<SemanticTypeId>,
}

impl SemanticTypeRegistry {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn from_types(
        type_defs: impl IntoIterator<Item = SemanticType>,
    ) -> Result<Self, SemanticTypeError> {
        let mut registry = Self::new();
        for type_def in type_defs {
            validate_type_id(type_def.id.as_str())?;
            if registry.types.contains_key(&type_def.id) {
                return Err(SemanticTypeError::DuplicateType(type_def.id.0));
            }
            registry.registration_order.push(type_def.id.clone());
            registry.types.insert(type_def.id.clone(), type_def);
        }
        registry.validate()?;
        Ok(registry)
    }

    pub fn from_ir_nodes(
        nodes: impl IntoIterator<Item = SemanticTypeIrNode>,
    ) -> Result<Self, SemanticTypeError> {
        let types = nodes
            .into_iter()
            .map(SemanticType::try_from)
            .collect::<Result<Vec<_>, _>>()?;
        Self::from_types(types)
    }

    pub fn standard() -> Self {
        let definitions = [
            ("Entity", None),
            ("Abstract", Some("Entity")),
            ("Concept", Some("Abstract")),
            ("Goal", Some("Abstract")),
            ("Constraint", Some("Abstract")),
            ("Concrete", Some("Entity")),
            ("Object", Some("Concrete")),
            ("Agent", Some("Concrete")),
            ("Process", Some("Entity")),
            ("Action", Some("Process")),
            ("Event", Some("Process")),
            ("Value", Some("Entity")),
            ("Number", Some("Value")),
            ("Text", Some("Value")),
            ("Boolean", Some("Value")),
            ("Vector", Some("Value")),
        ];
        let mut registry = Self::new();
        for (id, parent) in definitions {
            let type_def = match parent {
                Some(parent) => SemanticType::child(id, parent),
                None => SemanticType::root(id),
            };
            registry
                .register_type(type_def)
                .expect("standard semantic hierarchy must be valid");
        }
        registry
    }

    pub fn register_type(&mut self, type_def: SemanticType) -> Result<(), SemanticTypeError> {
        validate_type_id(type_def.id.as_str())?;
        if self.types.contains_key(&type_def.id) {
            return Err(SemanticTypeError::DuplicateType(type_def.id.0));
        }
        if type_def.parent.as_ref() == Some(&type_def.id) {
            return Err(SemanticTypeError::SelfInheritance(type_def.id.0));
        }
        if let Some(parent) = &type_def.parent {
            if !self.types.contains_key(parent) {
                return Err(SemanticTypeError::UnknownParent(parent.0.clone()));
            }
        }

        self.registration_order.push(type_def.id.clone());
        self.types.insert(type_def.id.clone(), type_def);
        if let Err(error) = self.validate() {
            let id = self
                .registration_order
                .pop()
                .expect("registered type order must contain inserted type");
            self.types.remove(&id);
            return Err(error);
        }
        Ok(())
    }

    pub fn get_type(&self, id: &SemanticTypeId) -> Option<&SemanticType> {
        self.types.get(id)
    }

    pub fn type_ids(&self) -> Vec<SemanticTypeId> {
        let mut ids = self.types.keys().cloned().collect::<Vec<_>>();
        ids.sort();
        ids
    }

    pub fn get_parent(&self, id: &SemanticTypeId) -> Option<&SemanticType> {
        self.types
            .get(id)
            .and_then(|type_def| type_def.parent.as_ref())
            .and_then(|parent| self.types.get(parent))
    }

    pub fn get_ancestors(
        &self,
        id: &SemanticTypeId,
    ) -> Result<Vec<SemanticTypeId>, SemanticTypeError> {
        let mut current = self.require_type(id)?;
        let mut ancestors = Vec::new();
        let mut visited = HashSet::from([id.clone()]);

        while let Some(parent_id) = &current.parent {
            if !visited.insert(parent_id.clone()) {
                let mut path = ancestors
                    .iter()
                    .map(ToString::to_string)
                    .collect::<Vec<_>>();
                path.push(parent_id.0.clone());
                return Err(SemanticTypeError::CircularInheritance(path));
            }
            ancestors.push(parent_id.clone());
            current = self
                .types
                .get(parent_id)
                .ok_or_else(|| SemanticTypeError::UnknownParent(parent_id.0.clone()))?;
        }
        Ok(ancestors)
    }

    pub fn get_descendants(
        &self,
        id: &SemanticTypeId,
    ) -> Result<Vec<SemanticTypeId>, SemanticTypeError> {
        self.require_type(id)?;
        let mut descendants = Vec::new();
        let mut queue = VecDeque::from([id.clone()]);

        while let Some(parent) = queue.pop_front() {
            for child in self.registration_order.iter().filter(|candidate| {
                self.types
                    .get(*candidate)
                    .and_then(|type_def| type_def.parent.as_ref())
                    == Some(&parent)
            }) {
                descendants.push(child.clone());
                queue.push_back(child.clone());
            }
        }
        Ok(descendants)
    }

    pub fn is_subtype_of(
        &self,
        child: &SemanticTypeId,
        parent: &SemanticTypeId,
    ) -> Result<bool, SemanticTypeError> {
        self.require_type(parent)?;
        Ok(child == parent || self.get_ancestors(child)?.contains(parent))
    }

    pub fn semantic_closure(
        &self,
        id: &SemanticTypeId,
    ) -> Result<Vec<SemanticTypeId>, SemanticTypeError> {
        let mut closure = vec![self.require_type(id)?.id.clone()];
        closure.extend(self.get_ancestors(id)?);
        Ok(closure)
    }

    pub fn derive_is_a(
        &self,
        id: &SemanticTypeId,
    ) -> Result<Vec<SemanticRelation>, SemanticTypeError> {
        Ok(self
            .get_ancestors(id)?
            .into_iter()
            .map(|ancestor| SemanticRelation::is_a(id.clone(), ancestor))
            .collect())
    }

    pub fn to_ir_nodes(&self) -> Vec<SemanticTypeIrNode> {
        self.registration_order
            .iter()
            .filter_map(|id| self.types.get(id))
            .map(SemanticTypeIrNode::from)
            .collect()
    }

    pub fn validate(&self) -> Result<(), SemanticTypeError> {
        for type_def in self.types.values() {
            validate_type_id(type_def.id.as_str())?;
            if type_def.parent.as_ref() == Some(&type_def.id) {
                return Err(SemanticTypeError::SelfInheritance(type_def.id.0.clone()));
            }
            if let Some(parent) = &type_def.parent {
                if !self.types.contains_key(parent) {
                    return Err(SemanticTypeError::UnknownParent(parent.0.clone()));
                }
            }
        }

        let mut ids = self.types.keys().cloned().collect::<Vec<_>>();
        ids.sort();
        for id in ids {
            self.validate_ancestry(&id)?;
        }
        Ok(())
    }

    fn require_type(&self, id: &SemanticTypeId) -> Result<&SemanticType, SemanticTypeError> {
        self.types
            .get(id)
            .ok_or_else(|| SemanticTypeError::TypeNotFound(id.0.clone()))
    }

    fn validate_ancestry(&self, start: &SemanticTypeId) -> Result<(), SemanticTypeError> {
        let mut positions = HashMap::<SemanticTypeId, usize>::new();
        let mut path = Vec::<SemanticTypeId>::new();
        let mut current = Some(start.clone());

        while let Some(id) = current {
            if let Some(position) = positions.get(&id) {
                let mut cycle = path[*position..]
                    .iter()
                    .map(ToString::to_string)
                    .collect::<Vec<_>>();
                cycle.push(id.0);
                return Err(SemanticTypeError::CircularInheritance(cycle));
            }
            positions.insert(id.clone(), path.len());
            path.push(id.clone());
            current = self.require_type(&id)?.parent.clone();
        }
        Ok(())
    }
}

fn validate_type_id(id: &str) -> Result<(), SemanticTypeError> {
    if id.trim().is_empty() {
        Err(SemanticTypeError::InvalidTypeId(id.to_string()))
    } else {
        Ok(())
    }
}
