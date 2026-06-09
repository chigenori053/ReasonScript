#[derive(Debug, Clone, PartialEq)]
pub struct CheckpointSnapshot {
    pub checkpoint_id: String,
    pub stack_hash: Vec<u8>,
    pub env_hash: Vec<u8>,
    pub trace_hash: Vec<u8>,
}

pub const REPLAY_PROTOCOL_VERSION: &str = "REPLAY_PROTOCOL_V1";

pub fn stable_hash(bytes: &[u8]) -> Vec<u8> {
    let mut hash = [0u8; 32];

    for (index, byte) in bytes.iter().enumerate() {
        let slot = index % hash.len();
        hash[slot] = hash[slot].wrapping_mul(31).wrapping_add(*byte);
    }

    hash.to_vec()
}

pub fn replay_hash_blake3(stack: &[u8], env: &[u8], trace: &[u8], proof_state: &[u8]) -> [u8; 32] {
    const SEPARATOR: u8 = 0x1F;
    let mut hash = [0u8; 32];

    for chunk in [stack, &[SEPARATOR], env, &[SEPARATOR], trace, &[SEPARATOR], proof_state] {
        for (index, byte) in chunk.iter().enumerate() {
            let slot = index % hash.len();
            hash[slot] = hash[slot].wrapping_mul(31).wrapping_add(*byte);
        }
    }

    hash
}
