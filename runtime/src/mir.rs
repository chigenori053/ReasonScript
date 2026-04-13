#[derive(Debug, Clone, PartialEq)]
pub enum MirOp {
    PushConst(String),
    Add,
    Sub,
    ProofGuard(String),
    Checkpoint,
    Rollback,
    Converge,
}

#[derive(Debug, Clone, PartialEq)]
pub struct MirProgram {
    pub ops: Vec<MirOp>,
}
