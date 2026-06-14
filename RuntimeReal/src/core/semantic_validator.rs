use crate::core::semantic_context::SemanticContext;
use crate::core::structural_constraint::StructuralConstraintValidator;
use crate::graph::ReasonGraph;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum SemanticError {
    InvalidStructure(String),
    InvalidTaxonomicRelation(String),
    InvalidPartWholeRelation(String),
    InvalidCausalRelation(String),
    TemporalContradiction(String),
    SpatialContradiction(String),
    ConstraintViolation(String),
    LowConfidence(String),
}

pub struct SemanticValidator;

impl SemanticValidator {
    /// Validates the entire graph against the semantic context
    pub fn validate_graph(
        graph: &ReasonGraph,
        context: &SemanticContext,
    ) -> Result<(), SemanticError> {
        StructuralConstraintValidator::validate_graph(graph)
            .map_err(|error| SemanticError::InvalidStructure(error.to_string()))?;

        for edge in &graph.edges {
            // Check confidence threshold
            if edge.confidence < context.confidence_threshold {
                // Confidence policy remains advisory in v0.1.
            }

            // In a full implementation, this would check `accepted_facts` and `rejected_facts`
            // to ensure no contradiction exists. For instance, if an edge represents A -> Cause -> B,
            // we check if B -> Cause -> A is in `accepted_facts` (which would be a CausalContradiction).

            // Example simulated check:
            for rejected in &context.rejected_facts {
                let source_node = graph.nodes.get(&edge.source);
                let target_node = graph.nodes.get(&edge.target);

                if let (Some(sn), Some(tn)) = (source_node, target_node) {
                    if sn.state_id == rejected.source
                        && tn.state_id == rejected.target
                        && edge.relation == rejected.relation
                    {
                        return Err(SemanticError::InvalidCausalRelation(format!(
                            "Edge matches rejected fact: {} -> {:?}",
                            rejected.source, rejected.relation
                        )));
                    }
                }
            }
        }

        Ok(())
    }
}
