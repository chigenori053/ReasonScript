use reasonscript_dto::{
    ExecutionPlan, GoalSpec, InferenceResult, InferenceStatus, PlanPath, PlanStep, Proof, ReasonIR,
    StateSnapshot, Trace, TraceEvent, TransactionRecord, TransactionStatus, TransitionSpec,
    Violation, REASON_IR_VERSION,
};
use serde_json::json;

fn state(id: &str) -> StateSnapshot {
    StateSnapshot::new(id, "symbolic", json!({ "identity": id }))
}

#[test]
fn reason_ir_round_trips() {
    let ir = ReasonIR::new(
        state("Dog"),
        GoalSpec::new("reach_state", "Animal"),
        vec![TransitionSpec::new("t1", "Dog", "IsA", "Animal")],
    );
    let json = ir.to_json_pretty().unwrap();
    assert_eq!(ReasonIR::from_json(&json).unwrap(), ir);
}

#[test]
fn level_four_public_dtos_round_trip() {
    let plan = ExecutionPlan::new(
        vec![PlanStep {
            step_id: "step-1".to_string(),
            transition_id: "t1".to_string(),
            source: "Dog".to_string(),
            target: "Animal".to_string(),
        }],
        vec![PlanPath {
            step_ids: vec!["alternative-1".to_string()],
            expected_cost: 2.0,
        }],
        1.0,
        vec!["evidence://taxonomy".to_string()],
        "planner/0.1",
    )
    .unwrap();
    let encoded = serde_json::to_string(&plan).unwrap();
    assert_eq!(
        serde_json::from_str::<ExecutionPlan>(&encoded).unwrap(),
        plan
    );

    let result = InferenceResult {
        status: InferenceStatus::Completed,
        final_state: state("Animal"),
        state_deltas: Vec::new(),
        proof: Some(Proof {
            selected_step_ids: vec!["step-1".to_string()],
            evidence_refs: vec!["evidence://taxonomy".to_string()],
        }),
        violations: vec![Violation {
            constraint_id: "none".to_string(),
            message: "no violation".to_string(),
        }],
        alternatives: Vec::new(),
        trace_id: "trace-1".to_string(),
    };
    let encoded = serde_json::to_string(&result).unwrap();
    assert_eq!(
        serde_json::from_str::<InferenceResult>(&encoded).unwrap(),
        result
    );

    let trace = Trace {
        request_id: "request-1".to_string(),
        reason_ir_version: REASON_IR_VERSION.to_string(),
        planner_version: Some("planner/0.1".to_string()),
        policy_version: "policy/0.1".to_string(),
        events: vec![TraceEvent::EvidenceObserved {
            evidence_ref: "evidence://taxonomy".to_string(),
        }],
    };
    let encoded = serde_json::to_string(&trace).unwrap();
    assert_eq!(serde_json::from_str::<Trace>(&encoded).unwrap(), trace);

    let record = TransactionRecord {
        transaction_id: "tx-1".to_string(),
        execution_plan_id: "plan-1".to_string(),
        candidate_id: "candidate-1".to_string(),
        delta_id: Some("delta-1".to_string()),
        status: TransactionStatus::Committed,
        commit_timestamp: Some(u64::MAX),
        validation_failures: Vec::new(),
        source_delta_id: None,
    };
    let encoded = serde_json::to_string(&record).unwrap();
    assert_eq!(
        serde_json::from_str::<TransactionRecord>(&encoded).unwrap(),
        record
    );
}
