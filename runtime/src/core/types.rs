use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum Type {
    Concept,
    Goal,
    Constraint,
    Fact,
    Action,
}
