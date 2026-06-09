use crate::executor::Executor;
use crate::ir::TensorIR;
use ndarray::Array2;

pub struct ConvergenceEngine;

impl ConvergenceEngine {
    pub fn converge(ir: &TensorIR, threshold: f64, max_iters: usize) -> Array2<f64> {
        let mut current = ir.state_matrix.clone();
        for _ in 0..max_iters {
            let next = Executor::execute(&TensorIR {
                state_matrix: current.clone(),
                transition_ops: ir.transition_ops.clone(),
            });
            let diff = (&next - &current).mapv(|x| x.powi(2)).sum().sqrt();
            current = next;
            if diff < threshold {
                break;
            }
        }
        current
    }
}
