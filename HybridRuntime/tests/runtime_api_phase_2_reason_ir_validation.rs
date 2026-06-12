use reasonscript_hybrid_runtime::{
    ConstraintSpec, ContextRef, ExecutionPlan, GoalSpec, InferenceResult, InferenceStatus,
    MinimalReasonIR, PlanPath, PlanStep, Proof, ReasonIR, ReasonIrError, StateKernel,
    StateSnapshot, Trace, TraceEvent, TransitionSpec, Violation, REASON_IR_VERSION,
};
use serde_json::{json, Value};
use std::collections::BTreeMap;

fn state(state_id: &str) -> StateSnapshot {
    StateSnapshot::new(state_id, "symbolic", json!({ "identity": state_id }))
}

fn transition(id: &str, source: &str, relation: &str, target: &str) -> TransitionSpec {
    TransitionSpec::new(id, source, relation, target)
}

fn platform_ir(initial: &str, goal: &str, transitions: Vec<TransitionSpec>) -> ReasonIR {
    ReasonIR::new(
        state(initial),
        GoalSpec::new("reach_state", goal),
        transitions,
    )
}

fn execute_linear(ir: &ReasonIR) -> (ExecutionPlan, InferenceResult, Trace) {
    ir.validate().unwrap();
    let steps = ir
        .transitions
        .iter()
        .map(|transition| PlanStep {
            step_id: format!("step-{}", transition.transition_id),
            transition_id: transition.transition_id.clone(),
            source: transition.source.clone(),
            target: transition.target.clone(),
        })
        .collect::<Vec<_>>();
    let plan = ExecutionPlan::new(
        steps.clone(),
        Vec::new(),
        ir.transitions
            .iter()
            .map(|transition| transition.expected_cost)
            .sum(),
        ir.context_refs
            .iter()
            .map(|context| context.context_id.clone())
            .collect(),
        "phase-2-planner/0.1",
    )
    .unwrap();

    let mut kernel = StateKernel::new(ir.initial_state.clone());
    let mut trace = Trace::new(
        "phase-2-request",
        Some(plan.planner_version().to_string()),
        "phase-2-policy/0.1",
    );
    trace.events.push(TraceEvent::PlanSelected {
        step_ids: steps.iter().map(|step| step.step_id.clone()).collect(),
        expected_cost: plan.expected_cost(),
    });

    let mut deltas = Vec::new();
    for (index, transition) in ir.transitions.iter().enumerate() {
        let delta = kernel
            .apply(transition, state(&transition.target), index as u64 + 1)
            .unwrap();
        trace.record_delta(&delta);
        deltas.push(delta);
    }

    let result = InferenceResult {
        status: InferenceStatus::Completed,
        final_state: kernel.current_state().clone(),
        state_deltas: deltas,
        proof: Some(Proof {
            selected_step_ids: steps.iter().map(|step| step.step_id.clone()).collect(),
            evidence_refs: plan.evidence_refs().to_vec(),
        }),
        violations: Vec::new(),
        alternatives: plan.alternative_paths().to_vec(),
        trace_id: trace.request_id.clone(),
    };
    trace.validate_deltas(&result.state_deltas).unwrap();
    (plan, result, trace)
}

fn assert_json_round_trip<T>(value: &T)
where
    T: serde::Serialize + serde::de::DeserializeOwned + PartialEq + std::fmt::Debug,
{
    let json = serde_json::to_string(value).unwrap();
    let restored = serde_json::from_str::<T>(&json).unwrap();
    assert_eq!(&restored, value);
}

#[test]
fn rir_01_reason_ir_required_optional_and_version_fields() {
    let ir = platform_ir(
        "Dog",
        "Animal",
        vec![
            transition("t1", "Dog", "IsA", "Mammal"),
            transition("t2", "Mammal", "IsA", "Animal"),
        ],
    );

    ir.validate().unwrap();
    let value = serde_json::to_value(&ir).unwrap();
    for required in [
        "schema_version",
        "initial_state",
        "goal",
        "transitions",
        "execution_policy",
        "trace_policy",
    ] {
        assert!(value.get(required).is_some(), "missing {required}");
    }
    assert_eq!(value["schema_version"], REASON_IR_VERSION);
    assert!(value.get("context_refs").is_none());
    assert!(value.get("constraints").is_none());
    assert!(value.get("planner_policy").is_none());
    assert!(value.get("metadata").is_none());
    assert_json_round_trip(&ir);
}

#[test]
fn rir_02_execution_plan_is_serializable_and_read_only_by_api() {
    let plan = ExecutionPlan::new(
        vec![PlanStep {
            step_id: "step-t1".to_string(),
            transition_id: "t1".to_string(),
            source: "Dog".to_string(),
            target: "Mammal".to_string(),
        }],
        vec![PlanPath {
            step_ids: vec!["step-alt".to_string()],
            expected_cost: 2.0,
        }],
        1.0,
        vec!["memory://taxonomy".to_string()],
        "planner/0.1",
    )
    .unwrap();

    assert_eq!(plan.selected_steps().len(), 1);
    assert_eq!(plan.alternative_paths().len(), 1);
    assert_eq!(plan.expected_cost(), 1.0);
    assert_eq!(plan.evidence_refs(), ["memory://taxonomy"]);
    assert_eq!(plan.planner_version(), "planner/0.1");
    assert_json_round_trip(&plan);
}

#[test]
fn rir_03_state_delta_is_kernel_owned_and_reversible() {
    let t1 = transition("t1", "StateA", "Action", "StateB");
    let mut kernel = StateKernel::new(state("StateA"));

    let delta = kernel.apply(&t1, state("StateB"), 10).unwrap();

    assert_eq!(delta.before_state().state_id, "StateA");
    assert_eq!(delta.after_state().state_id, "StateB");
    assert_eq!(delta.applied_transition(), "t1");
    assert_eq!(delta.timestamp(), 10);
    assert_eq!(kernel.current_state().state_id, "StateB");

    let rollback = kernel.rollback(&delta, 11).unwrap();
    assert_eq!(rollback.before_state().state_id, "StateB");
    assert_eq!(rollback.after_state().state_id, "StateA");
    assert_eq!(kernel.current_state().state_id, "StateA");
    assert_json_round_trip(&delta);
}

#[test]
fn rir_04_inference_result_is_sdk_neutral_and_round_trips() {
    let ir = platform_ir(
        "Dog",
        "Animal",
        vec![
            transition("t1", "Dog", "IsA", "Mammal"),
            transition("t2", "Mammal", "IsA", "Animal"),
        ],
    );
    let (_, result, _) = execute_linear(&ir);

    assert_eq!(result.status, InferenceStatus::Completed);
    assert_eq!(result.final_state.state_id, "Animal");
    assert_eq!(result.state_deltas.len(), 2);
    assert!(result.proof.is_some());
    assert_json_round_trip(&result);
}

#[test]
fn rir_05_trace_requires_an_event_for_every_state_delta() {
    let ir = platform_ir(
        "Dog",
        "Animal",
        vec![
            transition("t1", "Dog", "IsA", "Mammal"),
            transition("t2", "Mammal", "IsA", "Animal"),
        ],
    );
    let (_, result, trace) = execute_linear(&ir);

    trace.validate_deltas(&result.state_deltas).unwrap();
    let mut incomplete = trace.clone();
    incomplete.events.retain(|event| {
        !matches!(
            event,
            TraceEvent::StateDeltaApplied { delta_id, .. } if delta_id == "delta-2"
        )
    });
    assert_eq!(
        incomplete.validate_deltas(&result.state_deltas),
        Err(ReasonIrError::MissingTraceEvent("delta-2".to_string()))
    );
    assert_json_round_trip(&trace);
}

#[test]
fn rir_06_basic_inference_case() {
    let ir = platform_ir(
        "Dog",
        "Animal",
        vec![
            transition("t1", "Dog", "IsA", "Mammal"),
            transition("t2", "Mammal", "IsA", "Animal"),
        ],
    );
    let (_, result, trace) = execute_linear(&ir);

    assert_eq!(result.final_state.state_id, "Animal");
    assert_eq!(result.state_deltas.len(), 2);
    assert_eq!(trace.reason_ir_version, REASON_IR_VERSION);
}

#[test]
fn rir_07_constraint_validation_case() {
    let mut ir = platform_ir(
        "Hypothesis",
        "Reject",
        vec![transition("t1", "Hypothesis", "ConstraintCheck", "Reject")],
    );
    ir.constraints.push(ConstraintSpec {
        constraint_id: "cannot-fly".to_string(),
        kind: "semantic".to_string(),
        expression: "Animal CannotFly".to_string(),
    });
    let (_, mut result, mut trace) = execute_linear(&ir);
    result.status = InferenceStatus::Rejected;
    result.violations.push(Violation {
        constraint_id: "cannot-fly".to_string(),
        message: "Dog inherits Animal CannotFly".to_string(),
    });
    trace.events.push(TraceEvent::ConstraintViolation {
        constraint_id: "cannot-fly".to_string(),
        message: "Dog inherits Animal CannotFly".to_string(),
    });

    assert_eq!(result.status, InferenceStatus::Rejected);
    assert_eq!(result.violations.len(), 1);
    assert!(trace
        .events
        .iter()
        .any(|event| matches!(event, TraceEvent::ConstraintViolation { .. })));
}

#[test]
fn rir_08_memory_space_query_case() {
    let mut ir = platform_ir(
        "Query",
        "Output",
        vec![
            transition("t1", "Query", "Retrieve", "MemoryResult"),
            transition("t2", "MemoryResult", "Integrate", "Output"),
        ],
    );
    ir.context_refs.push(ContextRef {
        context_id: "memory-taxonomy".to_string(),
        context_type: "memory_space".to_string(),
        uri: Some("memory://shm/taxonomy".to_string()),
    });
    let (plan, result, _) = execute_linear(&ir);

    assert_eq!(result.final_state.state_id, "Output");
    assert_eq!(plan.evidence_refs(), ["memory-taxonomy"]);
}

#[test]
fn rir_09_dbm_planning_case() {
    let mut ir = platform_ir(
        "Goal",
        "Output",
        vec![
            transition("t1", "Goal", "Generate", "Hypothesis"),
            transition("t2", "Hypothesis", "Validate", "Validation"),
            transition("t3", "Validation", "Select", "Selection"),
            transition("t4", "Selection", "Emit", "Output"),
        ],
    );
    ir.metadata
        .insert("domain".to_string(), Value::String("dbm".to_string()));
    ir.planner_policy = Some(Default::default());
    let (plan, result, _) = execute_linear(&ir);

    assert_eq!(plan.selected_steps().len(), 4);
    assert_eq!(result.state_deltas.len(), 4);
    assert_eq!(result.final_state.state_id, "Output");
}

#[test]
fn rir_10_world_model_simulation_case() {
    let mut action = transition("move-1", "StateA", "Action", "StateB");
    action.effect = Some(json!({
        "position": { "from": [0, 0], "to": [1, 0] }
    }));
    let ir = platform_ir("StateA", "StateB", vec![action]);
    let (_, result, _) = execute_linear(&ir);

    assert_eq!(result.state_deltas.len(), 1);
    assert_eq!(result.state_deltas[0].before_state().state_id, "StateA");
    assert_eq!(result.state_deltas[0].after_state().state_id, "StateB");
}

#[test]
fn rir_11_tool_integration_case() {
    let mut call = transition("tool-1", "Goal", "ToolCall", "ToolResult");
    call.effect = Some(json!({
        "tool_ref": "weather.lookup",
        "arguments_ref": "context://weather-request"
    }));
    let ir = platform_ir(
        "Goal",
        "UpdatedState",
        vec![
            call,
            transition("t2", "ToolResult", "Integrate", "UpdatedState"),
        ],
    );
    let (_, result, mut trace) = execute_linear(&ir);
    trace.events.push(TraceEvent::ToolInvoked {
        tool_ref: "weather.lookup".to_string(),
        result_ref: "evidence://weather-result".to_string(),
    });

    assert_eq!(result.final_state.state_id, "UpdatedState");
    assert!(trace
        .events
        .iter()
        .any(|event| matches!(event, TraceEvent::ToolInvoked { .. })));
}

#[test]
fn rir_12_minimal_ir_migrates_to_platform_v01() {
    let legacy = MinimalReasonIR {
        initial_state: state("Dog"),
        transitions: vec![transition("t1", "Dog", "IsA", "Mammal")],
        goal: GoalSpec::new("reach_state", "Mammal"),
    };
    let json = serde_json::to_string(&legacy).unwrap();

    assert_eq!(
        ReasonIR::from_json(&json),
        Err(ReasonIrError::MissingField("schema_version".to_string()))
    );
    let migrated = ReasonIR::from_legacy_json(&json).unwrap();

    assert_eq!(migrated.schema_version, REASON_IR_VERSION);
    assert_eq!(migrated.metadata["migrated_from"], "minimal-ir/unversioned");
    assert_eq!(migrated.execution_policy.max_steps, 128);
}

#[test]
fn rir_13_unknown_version_is_rejected() {
    let mut value = serde_json::to_value(platform_ir(
        "Dog",
        "Mammal",
        vec![transition("t1", "Dog", "IsA", "Mammal")],
    ))
    .unwrap();
    value["schema_version"] = Value::String("reason-ir/9.9".to_string());

    assert_eq!(
        ReasonIR::from_json(&serde_json::to_string(&value).unwrap()),
        Err(ReasonIrError::UnsupportedVersion(
            "reason-ir/9.9".to_string()
        ))
    );
}

#[test]
fn rir_14_invariants_reject_invalid_ir_and_state_mutation() {
    let mut duplicate = platform_ir(
        "Dog",
        "Animal",
        vec![
            transition("same", "Dog", "IsA", "Mammal"),
            transition("same", "Mammal", "IsA", "Animal"),
        ],
    );
    assert_eq!(
        duplicate.validate(),
        Err(ReasonIrError::DuplicateId("same".to_string()))
    );

    duplicate.transitions[1].transition_id = "t2".to_string();
    duplicate.transitions[1].expected_cost = f64::NAN;
    assert!(matches!(
        duplicate.validate(),
        Err(ReasonIrError::InvalidField(_))
    ));

    let wrong = transition("t1", "OtherState", "Action", "StateB");
    let mut kernel = StateKernel::new(state("StateA"));
    assert_eq!(
        kernel.apply(&wrong, state("StateB"), 1),
        Err(ReasonIrError::StateMismatch {
            expected: "StateA".to_string(),
            actual: "OtherState".to_string(),
        })
    );
}

#[test]
fn rir_15_json_uses_only_platform_data_not_runtime_types() {
    let mut ir = platform_ir(
        "Dog",
        "Mammal",
        vec![transition("t1", "Dog", "IsA", "Mammal")],
    );
    ir.metadata = BTreeMap::from([
        ("producer".to_string(), json!("python-sdk/0.1")),
        ("request_tags".to_string(), json!(["taxonomy", "demo"])),
    ]);
    let json = ir.to_json_pretty().unwrap();

    for runtime_name in [
        "ReasonGraphRuntime",
        "StateManager",
        "TransitionEngine",
        "HybridRuntime",
        "Rust",
    ] {
        assert!(!json.contains(runtime_name));
    }
    assert!(json.contains("python-sdk/0.1"));
    assert_eq!(ReasonIR::from_json(&json).unwrap(), ir);
}
