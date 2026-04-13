use std::fs;
use runtime::parser::parse;
use runtime::evaluator::evaluate;

#[test]
fn apply_updates_state() {
    let source = "apply patch_session_machine";
    let program = parse(source);
    let result = evaluate(&program);

    assert_eq!(result.current_state, "patch_session_machine");
    assert_eq!(result.previous_state, Some("INIT".to_string()));
}

#[test]
fn rollback_restores_previous_safe_state() {
    let source = fs::read_to_string("../examples/session_fix.rsn")
        .expect("failed to read example");

    let program = parse(&source);
    let result = evaluate(&program);

    assert_eq!(result.trace.len(), 6);
    assert_eq!(result.current_state, "INIT");
    assert_eq!(result.previous_state, Some("INIT".to_string()));
}
