use crate::hir::{HirNode, HirProgram};
use crate::mir::{MirOp, MirProgram};

pub fn lower_hir(hir: &HirProgram) -> MirProgram {
    let mut ops = Vec::new();

    for node in &hir.nodes {
        match node {
            HirNode::Number(value) => ops.push(MirOp::PushConst(value.to_string())),
            HirNode::Goal(_) => {}
            HirNode::Apply(value) => {
                ops.push(MirOp::PushConst(value.clone()));
                ops.push(MirOp::Checkpoint);
            }
            HirNode::ComputeAdd(left, right) => {
                ops.push(MirOp::PushConst(left.clone()));
                ops.push(MirOp::PushConst(right.clone()));
                ops.push(MirOp::Add);
            }
            HirNode::ComputeSub(left, right) => {
                ops.push(MirOp::PushConst(left.clone()));
                ops.push(MirOp::PushConst(right.clone()));
                ops.push(MirOp::Sub);
            }
            HirNode::Prove(proof) => ops.push(MirOp::ProofGuard(proof.clone())),
            HirNode::Converge(_) => ops.push(MirOp::Converge),
            HirNode::Rollback(_) => ops.push(MirOp::Rollback),
        }
    }

    MirProgram { ops }
}
