use crate::ir::TensorIR;
use ndarray::Array2;

pub struct Executor;

impl Executor {
    pub fn execute(ir: &TensorIR) -> Array2<f64> {
        let mut current = ir.state_matrix.clone();
        for op in &ir.transition_ops {
            match op {
                crate::ir::tensor_ir::TensorOp::Add(mat) => {
                    current += mat;
                }
                crate::ir::tensor_ir::TensorOp::Mul(mat) => {
                    current = current.dot(mat);
                }
                crate::ir::tensor_ir::TensorOp::Lerp { target, alpha } => {
                    current = &current * (1.0 - alpha) + target * *alpha;
                }
            }
        }
        current
    }
}
