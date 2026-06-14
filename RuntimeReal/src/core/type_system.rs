use crate::core::structural_constraint::StructuralConstraintValidator;
use crate::core::types::{RelationType, StateType};
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
        StructuralConstraintValidator::is_compatible(source, relation, target)
    }

    /// Perform a full static type check on the ReasonGraph
    pub fn check_graph(graph: &ReasonGraph) -> Result<(), TypeError> {
        for edge in &graph.edges {
            let source_node = graph.nodes.get(&edge.source).ok_or_else(|| TypeError {
                message: format!("Source node {} not found", edge.source),
            })?;
            let target_node = graph.nodes.get(&edge.target).ok_or_else(|| TypeError {
                message: format!("Target node {} not found", edge.target),
            })?;

            let source_state =
                graph
                    .states
                    .get(&source_node.state_id)
                    .ok_or_else(|| TypeError {
                        message: format!("Source state {} not found", source_node.state_id),
                    })?;
            let target_state =
                graph
                    .states
                    .get(&target_node.state_id)
                    .ok_or_else(|| TypeError {
                        message: format!("Target state {} not found", target_node.state_id),
                    })?;

            if !Self::is_compatible(
                source_state.state_type,
                edge.relation,
                target_state.state_type,
            ) {
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
