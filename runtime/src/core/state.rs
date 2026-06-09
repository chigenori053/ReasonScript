use crate::core::ReasonUnit;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct State {
    pub current: ReasonUnit,
    pub history: Vec<ReasonUnit>,
}

impl State {
    pub fn new(initial: ReasonUnit) -> Self {
        Self {
            current: initial,
            history: Vec::new(),
        }
    }

    pub fn update(&mut self, next: ReasonUnit) {
        self.history.push(std::mem::replace(&mut self.current, next));
    }
}
