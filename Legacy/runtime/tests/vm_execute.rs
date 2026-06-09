use runtime::mir::{MirOp, MirProgram};
use runtime::vm::execute;

#[test]
fn arithmetic_stack_execution_is_deterministic() {
    let program = MirProgram {
        ops: vec![
            MirOp::PushConst("1/2".into()),
            MirOp::PushConst("3/4".into()),
            MirOp::Add,
        ],
    };

    let result = execute(&program);

    assert_eq!(result.stack.last().map(String::as_str), Some("5/4"));
    assert!(result.trace.contains(&"ADD".to_string()));
    assert_eq!(result.current_state, "5/4");
}

#[test]
fn rollback_restores_checkpoint() {
    let program = MirProgram {
        ops: vec![
            MirOp::PushConst("42".into()),
            MirOp::Checkpoint,
            MirOp::PushConst("100".into()),
            MirOp::Rollback,
        ],
    };

    let result = execute(&program);

    assert_eq!(result.stack, vec!["42".to_string()]);
    assert_eq!(result.current_state, "42");
    assert_eq!(result.previous_state, Some("42".to_string()));
    assert!(result.trace.contains(&"ROLLBACK(vm)".to_string()));
}

#[test]
fn proof_guard_auto_recovers_from_zero_denominator() {
    let program = MirProgram {
        ops: vec![
            MirOp::PushConst("42".into()),
            MirOp::Checkpoint,
            MirOp::PushConst("1/0".into()),
            MirOp::ProofGuard("denominator_nonzero".into()),
        ],
    };

    let result = execute(&program);

    assert!(result.proof_failed);
    assert_eq!(result.stack, vec!["42".to_string()]);
    assert_eq!(result.current_state, "42");
    assert_eq!(result.previous_state, Some("42".to_string()));
    assert!(result.trace.contains(&"PROVE_FAIL: denominator_nonzero".to_string()));
    assert!(result.trace.contains(&"ROLLBACK(vm)".to_string()));
}

#[test]
fn identical_mir_replays_identically() {
    let program = MirProgram {
        ops: vec![
            MirOp::PushConst("2".into()),
            MirOp::Checkpoint,
            MirOp::PushConst("1/2".into()),
            MirOp::PushConst("3/4".into()),
            MirOp::Add,
            MirOp::Rollback,
        ],
    };

    let first = execute(&program);
    let second = execute(&program);

    assert_eq!(first, second);
}
