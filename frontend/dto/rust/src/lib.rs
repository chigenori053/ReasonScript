use serde::{Deserialize, Serialize};
use serde_json::Value;

pub const AST_VERSION: &str = "reasonscript-ast/0.1";

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(tag = "node_type")]
pub enum DeclarationNode {
    GoalNode {
        node_id: String,
        kind: String,
        target: String,
    },
    StateNode {
        node_id: String,
        state_id: String,
        state_type: String,
        data: Value,
    },
    TransitionNode {
        node_id: String,
        transition_id: String,
        source: String,
        relation: String,
        target: String,
        #[serde(default = "default_expected_cost")]
        expected_cost: f64,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        guard: Option<String>,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        effect: Option<Value>,
    },
    ConstraintNode {
        node_id: String,
        constraint_id: String,
        kind: String,
        expression: String,
    },
    ContextNode {
        node_id: String,
        context_id: String,
        context_type: String,
        uri: String,
    },
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct MetadataNode {
    pub node_type: String,
    pub node_id: String,
    pub key: String,
    pub value: Value,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct ModuleNode {
    pub node_type: String,
    pub version: String,
    pub node_id: String,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub imports: Vec<String>,
    pub declarations: Vec<DeclarationNode>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub metadata: Vec<MetadataNode>,
}

fn default_expected_cost() -> f64 {
    1.0
}

pub fn round_trip_json(source: &str) -> Result<String, serde_json::Error> {
    let document: ModuleNode = serde_json::from_str(source)?;
    serde_json::to_string(&document)
}
