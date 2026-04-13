use std::fs;
use runtime::ast::{Proof, Statement, Symbol, Value};
use runtime::evaluator::evaluate;
use runtime::parser::parse;

#[test]
fn parser_assigns_typed_payloads() {
    let source = "goal preserve_session_consistency\nprove deterministic_state_transition\napply patch_session_machine";
    let program = parse(source);

    assert!(matches!(&program.statements[0], Statement::Goal(Symbol(_))));
    assert!(matches!(&program.statements[1], Statement::Prove(Proof(_))));
    assert!(matches!(
        &program.statements[2],
        Statement::Apply(Value::Symbol(Symbol(_)))
    ));
}

#[test]
fn evaluator_state_semantics_unchanged() {
    let source = fs::read_to_string("../examples/session_fix.rsn")
        .expect("failed to read example");

    let program = parse(&source);
    let result = evaluate(&program);

    assert_eq!(result.trace.len(), 6);
    assert_eq!(result.current_state, "INIT");
    assert!(!result.proof_failed);
}
