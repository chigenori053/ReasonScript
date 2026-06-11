use reasonscript_hybrid_runtime::{
    HybridReasonUnit, HybridRuntime, RuntimeError, State, TraceEventKind, Transition,
    TransitionCandidate,
};

fn runtime(identity: &str, test_id: &str) -> HybridRuntime {
    let mut runtime = HybridRuntime::new(HybridReasonUnit::new(State::stable(identity)));
    runtime.set_trace_test_id(test_id);
    runtime
}

fn register_dog_branches(runtime: &mut HybridRuntime) {
    runtime
        .transition_engine
        .register_with_cost("Dog", "IsA", "Mammal", 0.50);
    runtime
        .transition_engine
        .register_with_cost("Dog", "IsPet", "Pet", 0.10);
    runtime
        .transition_engine
        .register_with_cost("Dog", "IsA", "Canine", 0.30);
}

#[test]
fn hru_b_01_multiple_outgoing_transition() {
    let mut runtime = runtime("Dog", "HRU-B-01");
    register_dog_branches(&mut runtime);

    let before = runtime.state_manager.current().clone();
    let outgoing = runtime.transition_engine.outgoing("Dog");

    assert_eq!(outgoing.len(), 3);
    assert_eq!(runtime.transition_engine.relation_count(), 3);
    assert_eq!(runtime.state_manager.current(), &before);
}

#[test]
fn hru_b_02_branch_selection() {
    let mut runtime = runtime("Dog", "HRU-B-02");
    register_dog_branches(&mut runtime);

    let next = runtime.decide_and_transition().unwrap();

    assert_eq!(next.as_stable().unwrap().identity, "Pet");
    let trace = &runtime.trace_logger.records()[0];
    assert_eq!(
        trace.selected_transition.as_ref().unwrap().relation,
        "IsPet"
    );
    assert_eq!(trace.alternative_transitions.len(), 2);
    assert_eq!(
        trace.decision_reason.as_deref(),
        Some("minimum expected transition cost")
    );
}

#[test]
fn hru_b_03_sequential_branch_chain() {
    let mut runtime = runtime("Dog", "HRU-B-03");
    register_dog_branches(&mut runtime);
    runtime
        .transition_engine
        .register("Pet", "RefinesTo", "CompanionAnimal");

    runtime.decide_and_transition().unwrap();
    runtime.transition(Transition::new("RefinesTo")).unwrap();

    assert_eq!(
        runtime
            .state_manager
            .current()
            .as_stable()
            .unwrap()
            .identity,
        "CompanionAnimal"
    );
    assert_eq!(runtime.trace_logger.records().len(), 2);
}

#[test]
fn hru_b_04_converging_transition() {
    let mut dog_runtime = runtime("Dog", "HRU-B-04/Dog");
    dog_runtime
        .transition_engine
        .register("Dog", "IsA", "Mammal");
    dog_runtime.transition(Transition::new("IsA")).unwrap();

    let mut wolf_runtime = runtime("Wolf", "HRU-B-04/Wolf");
    wolf_runtime
        .transition_engine
        .register("Wolf", "IsA", "Mammal");
    wolf_runtime.transition(Transition::new("IsA")).unwrap();

    assert_eq!(
        dog_runtime.state_manager.current().as_stable().unwrap(),
        wolf_runtime.state_manager.current().as_stable().unwrap()
    );
}

#[test]
fn hru_b_05_multi_hop_transition() {
    let mut runtime = runtime("Dog", "HRU-B-05");
    for (source, target) in [
        ("Dog", "Canine"),
        ("Canine", "Mammal"),
        ("Mammal", "Animal"),
        ("Animal", "LivingThing"),
    ] {
        runtime.transition_engine.register(source, "IsA", target);
    }

    for _ in 0..4 {
        runtime.transition(Transition::new("IsA")).unwrap();
    }

    assert_eq!(
        runtime
            .state_manager
            .current()
            .as_stable()
            .unwrap()
            .identity,
        "LivingThing"
    );
    assert_eq!(runtime.trace_logger.records().len(), 4);
}

#[test]
fn hru_b_06_multiple_reason_unit_network() {
    let mut runtime = runtime("Dog", "HRU-B-06");
    runtime
        .state_manager
        .register_unit("unit_b", HybridReasonUnit::new(State::stable("Mammal")));
    runtime
        .state_manager
        .register_unit("unit_c", HybridReasonUnit::new(State::stable("Animal")));

    assert_eq!(runtime.state_manager.unit_count(), 3);
}

#[test]
fn hru_b_07_cross_unit_relation() {
    let mut runtime = runtime("Dog", "HRU-B-07");
    runtime.transition_engine.register("Dog", "IsA", "Mammal");
    runtime
        .transition_engine
        .register("Mammal", "IsA", "Animal");

    assert_eq!(runtime.transition_engine.relation_count(), 2);
}

#[test]
fn hru_b_08_relation_query() {
    let mut runtime = runtime("Dog", "HRU-B-08");
    runtime.transition_engine.register("Dog", "IsA", "Mammal");

    assert_eq!(runtime.transition_engine.parents("Dog"), vec!["Mammal"]);
}

#[test]
fn hru_b_09_decision_driven_transition() {
    let mut runtime = runtime("Dog", "HRU-B-09");
    register_dog_branches(&mut runtime);

    runtime.decide_and_transition().unwrap();

    let trace = &runtime.trace_logger.records()[0];
    assert!(trace.selected_transition.is_some());
    assert_eq!(trace.available_transitions.len(), 3);
    assert_eq!(trace.transition_scores.len(), 3);
    assert!(trace.selected_to_next_score_gap.unwrap() > 0.0);
}

#[test]
fn hru_b_10_transition_conflict() {
    let mut runtime = runtime("StateX", "HRU-B-10");
    runtime
        .transition_engine
        .register_with_cost("StateX", "A", "Y", 0.25);
    runtime
        .transition_engine
        .register_with_cost("StateX", "B", "Z", 0.25);

    let result = runtime.decide_and_transition();

    assert_eq!(
        result,
        Err(RuntimeError::TransitionDecisionRequired {
            source: "StateX".to_string(),
            candidate_count: 2,
        })
    );
    assert_eq!(
        runtime
            .state_manager
            .current()
            .as_stable()
            .unwrap()
            .identity,
        "StateX"
    );
    let trace = &runtime.trace_logger.records()[0];
    assert_eq!(trace.trace_event_kind, TraceEventKind::TransitionConflict);
    assert_eq!(trace.available_transitions.len(), 2);
    assert!(trace.selected_transition.is_none());
    assert_eq!(trace.selected_to_next_score_gap, Some(0.0));
    assert!(trace
        .decision_reason
        .as_deref()
        .unwrap()
        .contains("decision required"));
}

#[test]
fn hru_b_11_trace_completeness() {
    let mut runtime = runtime("Dog", "HRU-B-11");
    register_dog_branches(&mut runtime);
    runtime.decide_and_transition().unwrap();

    let json = serde_json::to_value(runtime.trace_logger.records()).unwrap();
    let trace = json.as_array().unwrap()[0].as_object().unwrap();
    for field in [
        "test_id",
        "initial_state",
        "available_transitions",
        "selected_transition",
        "alternative_transitions",
        "decision_reason",
        "next_state",
        "trace_event_kind",
        "policy_version",
        "evaluator_version",
    ] {
        assert!(trace.contains_key(field), "missing trace field: {field}");
    }
    assert_eq!(
        runtime.trace_logger.records()[0].trace_event_kind,
        TraceEventKind::Transition
    );
}

#[test]
fn hru_b_12_graph_integrity() {
    let unit = HybridReasonUnit::new(State::stable("Dog"));
    let mut runtime = HybridRuntime::new(unit.clone());
    runtime
        .transition_engine
        .register_candidate(TransitionCandidate::new("Dog", "IsA", "Mammal", 0.1));
    runtime
        .transition_engine
        .register_candidate(TransitionCandidate::new("Dog", "IsPet", "Pet", 0.2));

    let serialized_unit = serde_json::to_value(&unit).unwrap();
    assert_eq!(
        serialized_unit
            .as_object()
            .unwrap()
            .keys()
            .cloned()
            .collect::<Vec<_>>(),
        vec!["state"]
    );
    assert_eq!(runtime.transition_engine.relation_count(), 2);
}
