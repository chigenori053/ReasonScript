pub fn verify_proof_state(proof_state: &[u8]) -> bool {
    !proof_state.windows("invalid".len()).any(|window| window == b"invalid")
}
