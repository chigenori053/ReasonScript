use crate::checkpoint::{replay_hash_blake3, stable_hash};
use crate::proof::verify_proof_state;

#[derive(Debug, Clone, PartialEq)]
pub struct BlockResult {
    pub stack: Vec<String>,
    pub env: Vec<u8>,
    pub trace: Vec<String>,
    pub checkpoint: Option<Vec<u8>>,
    pub proof_state: Option<Vec<u8>>,
    pub status: String,
}

#[derive(Debug, Clone, PartialEq)]
pub struct RollbackResult {
    pub stack: Vec<String>,
    pub env: Vec<u8>,
    pub trace: Vec<String>,
}

pub fn execute_block(ops: Vec<String>, stack: Vec<String>, env: Vec<u8>) -> Result<BlockResult, String> {
    let trace = ops
        .iter()
        .map(|op| format!("EXEC:{op}"))
        .collect::<Vec<_>>();

    Ok(BlockResult {
        stack,
        env,
        trace,
        checkpoint: None,
        proof_state: None,
        status: "ok".to_string(),
    })
}

pub fn rollback_to_checkpoint(checkpoint: Vec<u8>) -> Result<RollbackResult, String> {
    Ok(RollbackResult {
        stack: Vec::new(),
        env: checkpoint.clone(),
        trace: vec![format!("ROLLBACK:{}", checkpoint.len())],
    })
}

pub fn verify_proof(proof_state: Vec<u8>) -> Result<bool, String> {
    Ok(verify_proof_state(&proof_state))
}

pub fn replay_hash(trace: Vec<u8>) -> Vec<u8> {
    stable_hash(&trace)
}

pub fn serialize_checkpoint(state: Vec<u8>) -> Vec<u8> {
    state
}

pub fn deserialize_checkpoint(blob: Vec<u8>) -> Vec<u8> {
    blob
}

pub fn replay_hash_blake3_nif(
    stack: Vec<u8>,
    env: Vec<u8>,
    trace: Vec<u8>,
    proof_state: Vec<u8>,
) -> [u8; 32] {
    replay_hash_blake3(&stack, &env, &trace, &proof_state)
}
