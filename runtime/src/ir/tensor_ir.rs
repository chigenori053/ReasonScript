use ndarray::Array2;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TensorIR {
    pub state_matrix: Array2<f64>,
    pub transition_ops: Vec<TensorOp>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum TensorOp {
    Add(Array2<f64>),
    Mul(Array2<f64>),
    Lerp { target: Array2<f64>, alpha: f64 },
}
