use crate::core::types::{StateType, RelationType};
use crate::graph::ReasonGraph;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct TypeError {
    pub message: String,
}

pub struct TypeChecker;

impl TypeChecker {
    /// Check compatibility between source and target state types over a specific relation.
    pub fn is_compatible(source: StateType, relation: RelationType, target: StateType) -> bool {
        match relation {
            RelationType::IsA => {
                match (source, target) {
                    (StateType::Concept, StateType::Concept) => true,
                    (StateType::Object, StateType::Object) => true,
                    (StateType::Event, StateType::Event) => true,
                    // Subtyping logic could go here
                    _ => false,
                }
            }
            RelationType::PartOf => {
                match (source, target) {
                    (StateType::Object, StateType::Object) => true,
                    (StateType::Concept, StateType::Concept) => true,
                    _ => false,
                }
            }
            RelationType::Cause => {
                match (source, target) {
                    (StateType::Event, StateType::Event) => true,
                    (StateType::Action, StateType::Event) => true,
                    _ => false,
                }
            }
            RelationType::Similar => true, // Any -> Any
            RelationType::Constraint => {
                match (source, target) {
                    (StateType::Goal, StateType::Constraint) => true,
                    (StateType::Action, StateType::Constraint) => true,
                    _ => false,
                }
            }
            // Add more specific rules as needed
            _ => true, 
        }
    }

    /// Perform a full static type check on the ReasonGraph
    pub fn check_graph(graph: &ReasonGraph) -> Result<(), TypeError> {
        for edge in &graph.edges {
            let source_node = graph.nodes.get(&edge.source)
                .ok_or_else(|| TypeError { message: format!("Source node {} not found", edge.source) })?;
            let target_node = graph.nodes.get(&edge.target)
                .ok_or_else(|| TypeError { message: format!("Target node {} not found", edge.target) })?;
            
            let source_state = graph.states.get(&source_node.state_id)
                .ok_or_else(|| TypeError { message: format!("Source state {} not found", source_node.state_id) })?;
            let target_state = graph.states.get(&target_node.state_id)
                .ok_or_else(|| TypeError { message: format!("Target state {} not found", target_node.state_id) })?;
            
            if !Self::is_compatible(source_state.state_type, edge.relation, target_state.state_type) {
                return Err(TypeError {
                    message: format!(
                        "Invalid relation: {:?} --{:?}--> {:?}",
                        source_state.state_type, edge.relation, target_state.state_type
                    ),
                });
            }
        }
        Ok(())
    }
}
