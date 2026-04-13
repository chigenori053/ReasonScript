use std::fs;
use runtime::parser::parse;
use runtime::evaluator::evaluate;

#[test]
fn proof_failure_triggers_auto_rollback() {
    let source = fs::read_to_string("../examples/proof_failure.rsn")
        .expect("failed to read example");

    let program = parse(&source);
    let result = evaluate(&program);

    assert!(result.proof_failed);
    assert!(result.trace.contains(&"PROVE_FAIL: invalid_transition".to_string()));
    assert!(result.trace.contains(&"ROLLBACK(auto)".to_string()));
    assert_eq!(result.current_state, "INIT");
    assert_eq!(result.previous_state, Some("INIT".to_string()));
}

#[test]
fn valid_proof_keeps_state() {
    let source = "apply patch_session_machine\nprove deterministic_state_transition";
    let program = parse(source);
    let result = evaluate(&program);

    assert!(!result.proof_failed);
    assert!(!result.trace.contains(&"ROLLBACK(auto)".to_string()));
    assert_eq!(result.current_state, "patch_session_machine");
}
