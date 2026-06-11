use crate::core::semantic_constraint::SemanticConstraint;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SemanticContext {
    pub accepted_facts: Vec<SemanticConstraint>,
    pub rejected_facts: Vec<SemanticConstraint>,
    pub confidence_threshold: f64,
}

impl SemanticContext {
    pub fn new(confidence_threshold: f64) -> Self {
        Self {
            accepted_facts: Vec::new(),
            rejected_facts: Vec::new(),
            confidence_threshold,
        }
    }

    pub fn add_accepted_fact(&mut self, fact: SemanticConstraint) {
        self.accepted_facts.push(fact);
    }

    pub fn add_rejected_fact(&mut self, fact: SemanticConstraint) {
        self.rejected_facts.push(fact);
    }
}
