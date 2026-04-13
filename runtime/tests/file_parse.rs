use std::fs;
use runtime::ast::{Statement, Symbol, State};
use runtime::parser::parse;

#[test]
fn parses_session_fix_example_file() {
    let source = fs::read_to_string("../examples/session_fix.rsn")
        .expect("failed to read example");

    let program = parse(&source);

    assert_eq!(program.statements.len(), 6);

    assert_eq!(
        program.statements[0],
        Statement::Goal(Symbol("preserve_session_consistency".into()))
    );

    assert_eq!(
        program.statements[5],
        Statement::Rollback(State("previous_safe_state".into()))
    );
}
