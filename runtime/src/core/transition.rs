use crate::core::ReasonUnit;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum Transition {
    Addition(ReasonUnit),
    Subsumption(ReasonUnit),
    Refinement { target: ReasonUnit, alpha: f64 },
}
