use std::fs;

use runtime::ast::{BinaryOp, Statement, Value};
use runtime::evaluator::evaluate;
use runtime::parser::parse;

#[test]
fn parser_recognizes_compute_statements() {
    let program = parse("compute 1/2 + 3/4");

    assert_eq!(
        program.statements[0],
        Statement::Compute(BinaryOp::Add(
            Value::Rational(1, 2),
            Value::Rational(3, 4),
        ))
    );
}

#[test]
fn rational_normalization_is_canonical() {
    let program = parse("apply 6/8\napply -4/6");
    let result = evaluate(&program);

    assert_eq!(result.trace[0], "APPLY: 3/4");
    assert_eq!(result.trace[1], "APPLY: -2/3");
    assert_eq!(result.current_state, "-2/3");
    assert_eq!(result.previous_state, Some("3/4".to_string()));
}

#[test]
fn scalar_promotion_is_deterministic() {
    let nat_and_rational = evaluate(&parse("compute 2 + 1/2"));
    assert_eq!(nat_and_rational.current_state, "5/2");

    let nat_and_nat = evaluate(&parse("compute 2 + 3"));
    assert_eq!(nat_and_nat.current_state, "5");
}

#[test]
fn rollback_safe_numeric_failure_restores_previous_state() {
    let program = parse("apply patch_session_machine\ncompute 1/2 + 1/0");
    let result = evaluate(&program);

    assert!(result.proof_failed);
    assert!(result.trace.contains(&"PROVE_FAIL: denominator_nonzero".to_string()));
    assert!(result.trace.contains(&"ROLLBACK(auto)".to_string()));
    assert_eq!(result.current_state, "INIT");
    assert_eq!(result.previous_state, Some("INIT".to_string()));
}

#[test]
fn scalar_arithmetic_example_evaluates_to_normalized_rational() {
    let source = fs::read_to_string("../examples/scalar_arithmetic.rsn")
        .expect("failed to read scalar arithmetic example");
    let result = evaluate(&parse(&source));

    assert_eq!(result.current_state, "5/4");
    assert!(!result.proof_failed);
}
