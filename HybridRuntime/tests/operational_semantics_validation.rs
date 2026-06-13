use reasonscript_hybrid_runtime::{
    ExecutionPlan, GoalSpec, InferenceResult, InferenceStatus, PlanStep, Proof, ReasonIrError,
    StateSnapshot, Trace, TraceEvent, TransactionKernel, TransactionStatus, TransitionSpec,
    ValidationChecks, ValidationStatus,
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
            "operational-semantics-request",
            Some("planner/0.1".to_string()),
            "policy/0.1",
        ),
    )
}

#[test]
fn os_01_goal_is_not_consumed_or_mutated_by_execution() {
    let goal = GoalSpec::new("reach_state", "B");
    let original = goal.clone();
    let mut runtime = kernel("A");
    let candidate = runtime
        .prepare("tx-1", "plan-1", transition("t1", "A", "B"), state("B"))
        .unwrap();
    runtime
        .validate(candidate.candidate_id(), ValidationChecks::accepted())
        .unwrap();
    runtime.commit(candidate.candidate_id(), 1).unwrap();

    assert_eq!(goal, original);
    assert_eq!(goal.target, runtime.current_state().state_id);
}

#[test]
fn os_02_prepare_and_validation_do_not_mutate_committed_state() {
    let mut runtime = kernel("A");
    let candidate = runtime
        .prepare("tx-1", "plan-1", transition("t1", "A", "B"), state("B"))
        .unwrap();

    assert_eq!(runtime.current_state(), &state("A"));
    assert_eq!(
        runtime
            .validate(candidate.candidate_id(), ValidationChecks::accepted())
            .unwrap(),
        ValidationStatus::Accepted
    );
    assert_eq!(runtime.current_state(), &state("A"));
    assert!(runtime.deltas().is_empty());
}

#[test]
fn os_03_source_and_target_mismatches_are_rejected_before_commit() {
    let mut runtime = kernel("A");
    assert!(matches!(
        runtime.prepare("tx-1", "plan-1", transition("t1", "X", "B"), state("B")),
        Err(ReasonIrError::StateMismatch { .. })
    ));
    assert_eq!(runtime.current_state(), &state("A"));

    assert!(matches!(
        runtime.prepare("tx-2", "plan-1", transition("t1", "A", "B"), state("C")),
        Err(ReasonIrError::StateMismatch { .. })
    ));
    assert_eq!(runtime.current_state(), &state("A"));
}

#[test]
fn os_04_constraint_rejection_blocks_commit_and_records_violation_class() {
    let mut runtime = kernel("A");
    let candidate = runtime
        .prepare("tx-1", "plan-1", transition("t1", "A", "B"), state("B"))
        .unwrap();
    let mut checks = ValidationChecks::accepted();
    checks.constraint = false;

    assert_eq!(
        runtime.validate(candidate.candidate_id(), checks).unwrap(),
        ValidationStatus::Rejected
    );
    assert_eq!(
        runtime.commit(candidate.candidate_id(), 1),
        Err(ReasonIrError::CommitNotAllowed(
            candidate.candidate_id().to_string()
        ))
    );
    assert_eq!(runtime.current_state(), &state("A"));
    assert_eq!(
        runtime.records().last().unwrap().validation_failures,
        ["constraint"]
    );
}

#[test]
fn os_07_execution_plan_is_read_only_and_preserves_step_order() {
    let plan = ExecutionPlan::new(
        vec![
            PlanStep {
                step_id: "step-1".to_string(),
                transition_id: "t1".to_string(),
                source: "A".to_string(),
                target: "B".to_string(),
            },
            PlanStep {
                step_id: "step-2".to_string(),
                transition_id: "t2".to_string(),
                source: "B".to_string(),
                target: "C".to_string(),
            },
        ],
        Vec::new(),
        2.0,
        Vec::new(),
        "planner/0.1",
    )
    .unwrap();

    assert_eq!(plan.selected_steps()[0].transition_id, "t1");
    assert_eq!(plan.selected_steps()[1].transition_id, "t2");
    assert_eq!(plan.expected_cost(), 2.0);
}

#[test]
fn os_08_commits_form_a_complete_chain_and_rollback_is_a_new_delta() {
    let mut runtime = kernel("A");
    let first_candidate = runtime
        .prepare("tx-1", "plan-1", transition("t1", "A", "B"), state("B"))
        .unwrap();
    runtime
        .validate(
            first_candidate.candidate_id(),
            ValidationChecks::accepted(),
        )
        .unwrap();
    let first = runtime.commit(first_candidate.candidate_id(), 1).unwrap();

    let second_candidate = runtime
        .prepare("tx-2", "plan-1", transition("t2", "B", "C"), state("C"))
        .unwrap();
    runtime
        .validate(
            second_candidate.candidate_id(),
            ValidationChecks::accepted(),
        )
        .unwrap();
    let second = runtime.commit(second_candidate.candidate_id(), 2).unwrap();

    assert_eq!(first.after_state(), second.before_state());
    let reverse = runtime
        .rollback("tx-3", "plan-1", second.delta_id(), 3)
        .unwrap();
    assert_eq!(reverse.before_state(), second.after_state());
    assert_eq!(reverse.after_state(), second.before_state());
    assert_eq!(reverse.applied_transition(), "rollback:t2");
    assert_eq!(runtime.deltas().len(), 3);
    assert_eq!(
        runtime.records().last().unwrap().status,
        TransactionStatus::RolledBack
    );
}

#[test]
fn os_09_inference_result_references_final_state_deltas_and_trace() {
    let mut runtime = kernel("A");
    let candidate = runtime
        .prepare("tx-1", "plan-1", transition("t1", "A", "B"), state("B"))
        .unwrap();
    runtime
        .validate(candidate.candidate_id(), ValidationChecks::accepted())
        .unwrap();
    runtime.commit(candidate.candidate_id(), 1).unwrap();
    runtime.validate_trace_consistency().unwrap();

    let result = InferenceResult {
        status: InferenceStatus::Completed,
        final_state: runtime.current_state().clone(),
        state_deltas: runtime.deltas().to_vec(),
        proof: Some(Proof {
            selected_step_ids: vec!["step-1".to_string()],
            evidence_refs: Vec::new(),
        }),
        violations: Vec::new(),
        alternatives: Vec::new(),
        trace_id: runtime.trace().request_id.clone(),
    };

    assert_eq!(result.final_state.state_id, "B");
    assert_eq!(result.state_deltas.len(), 1);
    assert_eq!(result.trace_id, "operational-semantics-request");
}

#[test]
fn os_10_every_commit_has_a_matching_trace_event() {
    let mut runtime = kernel("A");
    let candidate = runtime
        .prepare("tx-1", "plan-1", transition("t1", "A", "B"), state("B"))
        .unwrap();
    runtime
        .validate(candidate.candidate_id(), ValidationChecks::accepted())
        .unwrap();
    let delta = runtime.commit(candidate.candidate_id(), 1).unwrap();

    assert!(runtime.trace().events.iter().any(|event| matches!(
        event,
        TraceEvent::StateDeltaApplied {
            delta_id,
            transition_id,
            transaction_id: Some(transaction_id),
        } if delta_id == delta.delta_id()
            && transition_id == "t1"
            && transaction_id == "tx-1"
    )));
    runtime.validate_trace_consistency().unwrap();
}
