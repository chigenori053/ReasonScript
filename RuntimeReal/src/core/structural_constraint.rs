use crate::core::types::{RelationType, StateType};
use crate::graph::ReasonGraph;
use std::fmt;
use uuid::Uuid;

pub type SemanticUnitType = StateType;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum StructuralConstraintError {
    MissingSourceNode {
        edge_id: Uuid,
        node_id: Uuid,
    },
    MissingTargetNode {
        edge_id: Uuid,
        node_id: Uuid,
    },
    MissingState {
        node_id: Uuid,
        state_id: Uuid,
    },
    UnsupportedUnitType {
        node_id: Uuid,
        unit_type: SemanticUnitType,
    },
    InvalidRelation {
        edge_id: Uuid,
        source_type: SemanticUnitType,
        relation: RelationType,
        target_type: SemanticUnitType,
    },
}

impl fmt::Display for StructuralConstraintError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::MissingSourceNode { edge_id, node_id } => {
                write!(
                    formatter,
                    "edge {edge_id} references missing source node {node_id}"
                )
            }
            Self::MissingTargetNode { edge_id, node_id } => {
                write!(
                    formatter,
                    "edge {edge_id} references missing target node {node_id}"
                )
            }
            Self::MissingState { node_id, state_id } => {
                write!(
                    formatter,
                    "node {node_id} references missing state {state_id}"
                )
            }
            Self::UnsupportedUnitType { node_id, unit_type } => {
                write!(
                    formatter,
                    "node {node_id} uses unsupported semantic unit type {unit_type:?}"
                )
            }
            Self::InvalidRelation {
                edge_id,
                source_type,
                relation,
                target_type,
            } => {
                write!(
                    formatter,
                    "edge {edge_id} violates SCV-1: \
                     {source_type:?} --{relation:?}--> {target_type:?}"
                )
            }
        }
    }
}

impl std::error::Error for StructuralConstraintError {}

pub struct StructuralConstraintValidator;

impl StructuralConstraintValidator {
    pub fn is_compatible(
        source: SemanticUnitType,
        relation: RelationType,
        target: SemanticUnitType,
    ) -> bool {
        match relation {
            RelationType::IsA => matches!(
                (source, target),
                (StateType::Concept, StateType::Concept) | (StateType::Object, StateType::Concept)
            ),
            RelationType::PartOf => matches!(
                (source, target),
                (StateType::Object, StateType::Object) | (StateType::Object, StateType::Concept)
            ),
            RelationType::Cause => matches!(
                (source, target),
                (StateType::Event, StateType::Event)
                    | (StateType::Action, StateType::Event)
                    | (StateType::Event, StateType::Attribute)
            ),
            RelationType::Similar => source == target && source != StateType::Unknown,
            RelationType::Constraint => {
                source == StateType::Constraint
                    && matches!(
                        target,
                        StateType::Goal | StateType::Action | StateType::Event
                    )
            }
            // Temporal, spatial, and dependency validation belong to later SCV specifications.
            RelationType::Temporal | RelationType::Spatial | RelationType::Dependency => true,
        }
    }

    pub fn validate_graph(graph: &ReasonGraph) -> Result<(), StructuralConstraintError> {
        for (node_id, node) in &graph.nodes {
            let state = graph.states.get(&node.state_id).ok_or(
                StructuralConstraintError::MissingState {
                    node_id: *node_id,
                    state_id: node.state_id,
                },
            )?;
            if state.state_type == StateType::Unknown {
                return Err(StructuralConstraintError::UnsupportedUnitType {
                    node_id: *node_id,
                    unit_type: state.state_type,
                });
            }
        }

        for edge in &graph.edges {
            let source_node = graph.nodes.get(&edge.source).ok_or(
                StructuralConstraintError::MissingSourceNode {
                    edge_id: edge.id,
                    node_id: edge.source,
                },
            )?;
            let target_node = graph.nodes.get(&edge.target).ok_or(
                StructuralConstraintError::MissingTargetNode {
                    edge_id: edge.id,
                    node_id: edge.target,
                },
            )?;
            let source_state = graph.states.get(&source_node.state_id).ok_or(
                StructuralConstraintError::MissingState {
                    node_id: source_node.id,
                    state_id: source_node.state_id,
                },
            )?;
            let target_state = graph.states.get(&target_node.state_id).ok_or(
                StructuralConstraintError::MissingState {
                    node_id: target_node.id,
                    state_id: target_node.state_id,
                },
            )?;

            if !Self::is_compatible(
                source_state.state_type,
                edge.relation,
                target_state.state_type,
            ) {
                return Err(StructuralConstraintError::InvalidRelation {
                    edge_id: edge.id,
                    source_type: source_state.state_type,
                    relation: edge.relation,
                    target_type: target_state.state_type,
                });
            }
        }

        Ok(())
    }
}
