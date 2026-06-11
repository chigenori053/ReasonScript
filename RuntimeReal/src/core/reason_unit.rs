use crate::core::types::UnitType;
use serde::{Deserialize, Serialize};
use uuid::Uuid;
use ndarray::Array1;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Default)]
pub struct ReasonUnitMetrics {
    pub activation_count: usize,
    pub closure_count: usize,
    pub propagation_count: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Default)]
pub struct IdentityMetrics {
    pub formation_count: usize,
    pub stability_score: f64,
    pub differentiation_score: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct ReasonUnit {
    pub id: Uuid,
    pub label: String,
    pub unit_type: UnitType,
    pub vector: Array1<f64>,
    pub metrics: ReasonUnitMetrics,
    pub identity_metrics: Option<IdentityMetrics>,
}

impl ReasonUnit {
    pub fn new(label: &str, unit_type: UnitType, vector: Array1<f64>) -> Self {
        Self {
            id: Uuid::new_v4(),
            label: label.to_string(),
            unit_type,
            vector,
            metrics: ReasonUnitMetrics::default(),
            identity_metrics: Some(IdentityMetrics::default()),
        }
    }

    pub fn zero(dim: usize, unit_type: UnitType) -> Self {
        Self {
            id: Uuid::new_v4(),
            label: "Identity".to_string(),
            unit_type,
            vector: Array1::zeros(dim),
            metrics: ReasonUnitMetrics::default(),
            identity_metrics: Some(IdentityMetrics::default()),
        }
    }

    pub fn increment_activation(&mut self) {
        self.metrics.activation_count += 1;
    }

    pub fn increment_closure(&mut self) {
        self.metrics.closure_count += 1;
    }

    pub fn increment_propagation(&mut self) {
        self.metrics.propagation_count += 1;
    }

    pub fn add(&self, other: &Self) -> Self {
        Self {
            id: Uuid::new_v4(),
            label: format!("({} + {})", self.label, other.label),
            unit_type: self.unit_type,
            vector: &self.vector + &other.vector,
            metrics: ReasonUnitMetrics::default(),
            identity_metrics: Some(IdentityMetrics::default()),
        }
    }

    pub fn sub(&self, other: &Self) -> Self {
        Self {
            id: Uuid::new_v4(),
            label: format!("({} - {})", self.label, other.label),
            unit_type: self.unit_type,
            vector: &self.vector - &other.vector,
            metrics: ReasonUnitMetrics::default(),
            identity_metrics: Some(IdentityMetrics::default()),
        }
    }

    pub fn neg(&self) -> Self {
        Self {
            id: Uuid::new_v4(),
            label: format!("-{}", self.label),
            unit_type: self.unit_type,
            vector: -&self.vector,
            metrics: ReasonUnitMetrics::default(),
            identity_metrics: Some(IdentityMetrics::default()),
        }
    }
}
