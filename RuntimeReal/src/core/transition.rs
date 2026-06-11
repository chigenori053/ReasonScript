use crate::core::ReasonUnit;
use crate::core::types::TransitionType;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum TransitionOp {
    Addition(ReasonUnit),
    Subsumption(ReasonUnit),
    Refinement { target: ReasonUnit, alpha: f64 },
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Transition {
    pub transition_type: TransitionType,
    pub op: TransitionOp,
}

impl Transition {
    pub fn new(transition_type: TransitionType, op: TransitionOp) -> Self {
        Self {
            transition_type,
            op,
        }
    }
}
