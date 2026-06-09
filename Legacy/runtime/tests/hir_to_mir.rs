use runtime::frontend::lower;
use runtime::middle::lower_hir;
use runtime::mir::MirOp;
use runtime::parser::parse;

#[test]
fn compute_lowers_to_stack_style_ops() {
    let hir = lower(&parse("compute 1/2 + 3/4"));
    let mir = lower_hir(&hir);

    assert_eq!(
        mir.ops,
        vec![
            MirOp::PushConst("1/2".into()),
            MirOp::PushConst("3/4".into()),
            MirOp::Add,
        ]
    );
}

#[test]
fn rollback_semantics_are_preserved_in_mir() {
    let hir = lower(&parse("apply 42\nrollback previous_safe_state"));
    let mir = lower_hir(&hir);

    assert!(mir.ops.contains(&MirOp::Checkpoint));
    assert!(mir.ops.contains(&MirOp::Rollback));
    assert_eq!(
        mir.ops,
        vec![
            MirOp::PushConst("42".into()),
            MirOp::Checkpoint,
            MirOp::Rollback,
        ]
    );
}

#[test]
fn converge_emits_terminal_join_op() {
    let hir = lower(&parse("goal scalar_math\nconverge verify_numeric_result"));
    let mir = lower_hir(&hir);

    assert_eq!(mir.ops.last(), Some(&MirOp::Converge));
}
