use crate::core::types::RelationType;
use crate::knowledge::{KnowledgeError, KnowledgeEvidence};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

pub const KNOWLEDGE_VERSION: &str = "kev-1/0.1-draft";

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SemanticRelation {
    pub source: Uuid,
    pub target: Uuid,
    pub relation: RelationType,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Knowledge {
    pub relation: SemanticRelation,
    pub evidence: KnowledgeEvidence,
    pub confidence: f64,
}

impl Knowledge {
    pub fn to_json_pretty(&self) -> Result<String, KnowledgeError> {
        serde_json::to_string_pretty(self)
            .map_err(|error| KnowledgeError::Serialization(error.to_string()))
    }
}
