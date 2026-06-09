use std::fs;

use runtime::ast::{Statement, Symbol, Value};
use runtime::evaluator::evaluate;
use runtime::parser::parse;

#[test]
fn parser_recognizes_numeric_literals() {
    let source = "apply 42\napply -3\napply 1/2\napply x";
    let program = parse(source);

    assert_eq!(program.statements[0], Statement::Apply(Value::Nat(42)));
    assert_eq!(program.statements[1], Statement::Apply(Value::Int(-3)));
    assert_eq!(program.statements[2], Statement::Apply(Value::Rational(1, 2)));
    assert_eq!(
        program.statements[3],
        Statement::Apply(Value::Symbol(Symbol("x".into())))
    );
}

#[test]
fn evaluator_preserves_numeric_apply_state() {
    let source = fs::read_to_string("../examples/scalar_literals.rsn")
        .expect("failed to read scalar example");

    let program = parse(&source);
    let result = evaluate(&program);

    assert_eq!(result.current_state, "1/2");
    assert_eq!(result.previous_state, Some("-3".to_string()));
    assert!(!result.proof_failed);
}
