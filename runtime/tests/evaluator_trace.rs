use std::fs;
use runtime::parser::parse;
use runtime::evaluator::evaluate;

#[test]
fn evaluates_session_fix_example_file() {
    let source = fs::read_to_string("../examples/session_fix.rsn")
        .expect("failed to read example");

    let program = parse(&source);
    let result = evaluate(&program);

    assert_eq!(result.trace.len(), 6);
    assert_eq!(result.trace[0], "GOAL: preserve_session_consistency");
    assert_eq!(result.trace[5], "ROLLBACK: previous_safe_state");
}
