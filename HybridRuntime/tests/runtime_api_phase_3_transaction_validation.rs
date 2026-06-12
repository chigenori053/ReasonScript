use reasonscript_hybrid_runtime::{
    ReasonIrError, StateSnapshot, Trace, TraceEvent, TransactionKernel, TransactionStatus,
    TransitionSpec, ValidationChecks, ValidationStatus,
};
use serde_json::json;

fn state(id: &str) -> StateSnapshot {
    StateSnapshot::new(id, "symbolic", json!({ "identity": id }))
}

fn transition(id: &str, source: &str, target: &str) -> TransitionSpec {
    TransitionSpec::new(id, source, "Action", target)
}

fn kernel(initial: &str) -> TransactionKernel {
    TransactionKernel::new(
        state(initial),
        Trace::new(
            "phase-3-request",
            Some("planner/0.1".to_string()),
            "policy/0.1",
        ),
    )
}

fn accepted_commit(
    kernel: &mut TransactionKernel,
    transaction_id: &str,
    plan_id: &str,
    transition: TransitionSpec,
    target: &str,
    timestamp: u64,
) -> reasonscript_hybrid_runtime::StateDelta {
    let candidate = kernel
        .prepare(transaction_id, plan_id, transition, state(target))
        .unwrap();
    assert_eq!(
        kernel
            .validate(candidate.candidate_id(), ValidationChecks::accepted())
            .unwrap(),
        ValidationStatus::Accepted
    );
    kernel.commit(candidate.candidate_id(), timestamp).unwrap()
}

#[test]
fn tx_01_basic_commit_generates_delta_trace_and_audit_record() {
    let mut kernel = kernel("StateA");
    let candidate = kernel
        .prepare(
            "tx-1",
            "plan-1",
            transition("t1", "StateA", "StateB"),
            state("StateB"),
        )
        .unwrap();

    assert_eq!(kernel.current_state().state_id, "StateA");
    assert_eq!(candidate.before_state().state_id, "StateA");
    kernel
        .validate(candidate.candidate_id(), ValidationChecks::accepted())
        .unwrap();
    let delta = kernel.commit(candidate.candidate_id(), 10).unwrap();

    assert_eq!(kernel.current_state().state_id, "StateB");
    assert_eq!(delta.before_state().state_id, "StateA");
    assert_eq!(delta.after_state().state_id, "StateB");
    assert!(kernel.trace().events.iter().any(|event| matches!(
        event,
        TraceEvent::StateDeltaApplied {
            delta_id,
            transaction_id: Some(transaction_id),
            ..
        } if delta_id == delta.delta_id() && transaction_id == "tx-1"
    )));
    assert_eq!(
        kernel.records().last().unwrap().status,
        TransactionStatus::Committed
    );
    kernel.validate_trace_consistency().unwrap();
}

#[test]
fn tx_02_constraint_rejection_preserves_state_and_blocks_commit() {
    let mut kernel = kernel("StateA");
    let candidate = kernel
        .prepare(
            "tx-1",
            "plan-1",
            transition("t1", "StateA", "StateB"),
            state("StateB"),
        )
        .unwrap();
    let mut checks = ValidationChecks::accepted();
    checks.constraint = false;

    assert_eq!(
        kernel.validate(candidate.candidate_id(), checks).unwrap(),
        ValidationStatus::Rejected
    );
    assert_eq!(
        kernel.commit(candidate.candidate_id(), 10),
        Err(ReasonIrError::CommitNotAllowed(
            candidate.candidate_id().to_string()
        ))
    );
    assert_eq!(kernel.current_state().state_id, "StateA");
    assert!(kernel.deltas().is_empty());
}

#[test]
fn tx_03_rollback_is_a_new_traced_reverse_delta() {
    let mut kernel = kernel("StateA");
    let delta = accepted_commit(
        &mut kernel,
        "tx-1",
        "plan-1",
        transition("t1", "StateA", "StateB"),
        "StateB",
        10,
    );

    let rollback = kernel
        .rollback("tx-rollback-1", "plan-1", delta.delta_id(), 11)
        .unwrap();

    assert_ne!(rollback.delta_id(), delta.delta_id());
    assert_eq!(rollback.before_state().state_id, "StateB");
    assert_eq!(rollback.after_state().state_id, "StateA");
    assert_eq!(delta.before_state().state_id, "StateA");
    assert_eq!(kernel.current_state().state_id, "StateA");
    kernel.validate_trace_consistency().unwrap();
}

#[test]
fn tx_04_trace_consistency_covers_every_commit() {
    let mut kernel = kernel("A");
    accepted_commit(
        &mut kernel,
        "tx-1",
        "plan-1",
        transition("t1", "A", "B"),
        "B",
        1,
    );
    accepted_commit(
        &mut kernel,
        "tx-2",
        "plan-1",
        transition("t2", "B", "C"),
        "C",
        2,
    );

    assert_eq!(kernel.deltas().len(), 2);
    kernel.validate_trace_consistency().unwrap();
}

#[test]
fn tx_05_execution_plan_is_not_owned_or_mutated_by_transaction_kernel() {
    let plan_id = String::from("immutable-plan-1");
    let original = plan_id.clone();
    let mut kernel = kernel("A");
    let candidate = kernel
        .prepare(
            "tx-1",
            plan_id.clone(),
            transition("t1", "A", "B"),
            state("B"),
        )
        .unwrap();

    assert_eq!(plan_id, original);
    assert_eq!(candidate.execution_plan_id(), "immutable-plan-1");
}

#[test]
fn tx_06_multiple_commits_form_a_consistent_delta_chain() {
    let mut kernel = kernel("A");
    let first = accepted_commit(
        &mut kernel,
        "tx-1",
        "plan-1",
        transition("t1", "A", "B"),
        "B",
        1,
    );
    let second = accepted_commit(
        &mut kernel,
        "tx-2",
        "plan-1",
        transition("t2", "B", "C"),
        "C",
        2,
    );

    assert_eq!(first.after_state(), second.before_state());
    assert_eq!(kernel.current_state().state_id, "C");
}

#[test]
fn tx_07_world_model_effect_commits_as_state_delta() {
    let mut action = transition("move-1", "WorldA", "WorldB");
    action.effect = Some(json!({ "position": { "from": [0, 0], "to": [1, 0] } }));
    let mut kernel = kernel("WorldA");

    let delta = accepted_commit(&mut kernel, "tx-world", "plan-world", action, "WorldB", 1);

    assert_eq!(delta.applied_transition(), "move-1");
    assert_eq!(delta.after_state().state_id, "WorldB");
}

#[test]
fn tx_08_tool_result_requires_validation_before_state_update() {
    let mut tool_transition = transition("tool-1", "AwaitingTool", "ToolIntegrated");
    tool_transition.effect = Some(json!({ "result_ref": "tool://weather/result-1" }));
    let mut kernel = kernel("AwaitingTool");
    let candidate = kernel
        .prepare(
            "tx-tool",
            "plan-tool",
            tool_transition,
            state("ToolIntegrated"),
        )
        .unwrap();

    assert_eq!(
        kernel.commit(candidate.candidate_id(), 1),
        Err(ReasonIrError::CommitNotAllowed(
            candidate.candidate_id().to_string()
        ))
    );
    kernel
        .validate(candidate.candidate_id(), ValidationChecks::accepted())
        .unwrap();
    kernel.commit(candidate.candidate_id(), 2).unwrap();
    assert_eq!(kernel.current_state().state_id, "ToolIntegrated");
}

#[test]
fn tx_09_candidate_transaction_and_rollback_reuse_are_rejected() {
    let mut kernel = kernel("A");
    let candidate = kernel
        .prepare("tx-1", "plan-1", transition("t1", "A", "B"), state("B"))
        .unwrap();
    kernel
        .validate(candidate.candidate_id(), ValidationChecks::accepted())
        .unwrap();
    let delta = kernel.commit(candidate.candidate_id(), 1).unwrap();

    assert!(matches!(
        kernel.commit(candidate.candidate_id(), 2),
        Err(ReasonIrError::CandidateAlreadyCommitted(_))
    ));
    assert!(matches!(
        kernel.prepare("tx-1", "plan-1", transition("t2", "B", "C"), state("C")),
        Err(ReasonIrError::DuplicateTransactionId(_))
    ));
    kernel
        .rollback("tx-2", "plan-1", delta.delta_id(), 3)
        .unwrap();
    assert!(matches!(
        kernel.rollback("tx-3", "plan-1", delta.delta_id(), 4),
        Err(ReasonIrError::DeltaAlreadyRolledBack(_))
    ));
}
