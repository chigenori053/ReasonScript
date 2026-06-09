use serde::{Deserialize, Serialize};
use uuid::Uuid;
use ndarray::Array1;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct ReasonUnit {
    pub id: Uuid,
    pub label: String,
    pub vector: Array1<f64>,
}

impl ReasonUnit {
    pub fn new(label: &str, vector: Array1<f64>) -> Self {
        Self {
            id: Uuid::new_v4(),
            label: label.to_string(),
            vector,
        }
    }

    pub fn zero(dim: usize) -> Self {
        Self {
            id: Uuid::new_v4(),
            label: "Identity".to_string(),
            vector: Array1::zeros(dim),
        }
    }

    pub fn add(&self, other: &Self) -> Self {
        Self {
            id: Uuid::new_v4(),
            label: format!("({} + {})", self.label, other.label),
            vector: &self.vector + &other.vector,
        }
    }

    pub fn sub(&self, other: &Self) -> Self {
        Self {
            id: Uuid::new_v4(),
            label: format!("({} - {})", self.label, other.label),
            vector: &self.vector - &other.vector,
        }
    }

    pub fn neg(&self) -> Self {
        Self {
            id: Uuid::new_v4(),
            label: format!("-{}", self.label),
            vector: -&self.vector,
        }
    }
}
