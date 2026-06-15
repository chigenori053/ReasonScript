use crate::knowledge::{
    Knowledge, KnowledgeError, KnowledgeEvidence, KnowledgeValidator, SemanticRelation,
};
use crate::semantic_simulation::SimulationResult;

#[derive(Debug, Clone, Default)]
pub struct KnowledgeGenerator {
    validator: KnowledgeValidator,
}

impl KnowledgeGenerator {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn generate(&self, result: &SimulationResult) -> Result<Knowledge, KnowledgeError> {
        self.validator.validate(result)?;

        let relation = result.trace.steps[0].relation;
        Ok(Knowledge {
            relation: SemanticRelation {
                source: result.path[0],
                target: result.path[result.path.len() - 1],
                relation,
            },
            evidence: KnowledgeEvidence {
                source_plan: result.source_plan.clone(),
                simulation_result: result.clone(),
            },
            confidence: result.confidence,
        })
    }
}
