use crate::core::types::UnitType;
use serde::{Deserialize, Serialize};
use uuid::Uuid;
use ndarray::Array1;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct ReasonUnit {
    pub id: Uuid,
    pub label: String,
    pub unit_type: UnitType,
    pub vector: Array1<f64>,
}

impl ReasonUnit {
    pub fn new(label: &str, unit_type: UnitType, vector: Array1<f64>) -> Self {
        Self {
            id: Uuid::new_v4(),
            label: label.to_string(),
            unit_type,
            vector,
        }
    }

    pub fn zero(dim: usize, unit_type: UnitType) -> Self {
        Self {
            id: Uuid::new_v4(),
            label: "Identity".to_string(),
            unit_type,
            vector: Array1::zeros(dim),
        }
    }

    pub fn add(&self, other: &Self) -> Self {
        Self {
            id: Uuid::new_v4(),
            label: format!("({} + {})", self.label, other.label),
            unit_type: self.unit_type,
            vector: &self.vector + &other.vector,
        }
    }

    pub fn sub(&self, other: &Self) -> Self {
        Self {
            id: Uuid::new_v4(),
            label: format!("({} - {})", self.label, other.label),
            unit_type: self.unit_type,
            vector: &self.vector - &other.vector,
        }
    }

    pub fn neg(&self) -> Self {
        Self {
            id: Uuid::new_v4(),
            label: format!("-{}", self.label),
            unit_type: self.unit_type,
            vector: -&self.vector,
        }
    }
}
