use reasonscript_hybrid_runtime::{
    AmbiguityEvaluator, Candidate, DecisionEngine, DecisionInput, Evidence, HybridReasonUnit,
    HybridRuntime, ResolutionOutcome, RiskPolicy, State, StateKind, StrategyKind, TraceEventKind,
    Transition,
};

fn candidate(identity: &str, probability: f64, vector: &[f64]) -> Candidate {
    Candidate::new(identity, probability, vector.to_vec())
}

fn candidates(probabilities: [f64; 3]) -> Vec<Candidate> {
    vec![
        candidate("Dog", probabilities[0], &[0.99, 0.99, 0.96, 0.18]),
        candidate("Wolf", probabilities[1], &[0.99, 0.96, 0.08, 0.96]),
        candidate("Fox", probabilities[2], &[0.99, 0.58, 0.06, 0.94]),
    ]
}

fn state_with(probabilities: [f64; 3], evidence: Vec<Evidence>) -> State {
    State::ambiguous(candidates(probabilities), evidence)
}

fn low_state() -> State {
    state_with(
        [0.95, 0.03, 0.02],
        vec![Evidence::supported("Domestic", vec![0.96, 0.08, 0.06])],
    )
}

fn medium_state() -> State {
    state_with(
        [0.60, 0.35, 0.05],
        vec![Evidence::supported("Canine", vec![0.99, 0.96, 0.58])],
    )
}

fn high_state() -> State {
    state_with(
        [0.45, 0.40, 0.15],
        vec![Evidence::supported("Canine", vec![0.99, 0.96, 0.58])],
    )
}

fn conflict_state() -> State {
    state_with(
        [0.718, 0.191, 0.091],
        vec![
            Evidence::supported("Pet", vec![0.97, 0.05, 0.04]),
            Evidence::supported("Wild", vec![0.18, 0.96, 0.94]),
            Evidence::supported("Canine", vec![0.99, 0.96, 0.58]),
        ],
    )
}

fn assert_required_trace_fields(runtime: &HybridRuntime) {
    let json = serde_json::to_value(runtime.trace_logger.records()).unwrap();
    let record = json
        .as_array()
        .unwrap()
        .last()
        .unwrap()
        .as_object()
        .unwrap();
    for field in [
        "test_id",
        "initial_state",
        "candidate_distribution",
        "ambiguity_observation",
        "selected_strategy",
        "alternative_strategies",
        "strategy_scores",
        "decision_reason",
        "resolution_outcome",
        "transition_relation",
        "next_state",
        "policy_version",
        "evaluator_version",
    ] {
        assert!(record.contains_key(field), "missing trace field: {field}");
    }
}

#[test]
fn hru_01_stable_reason_unit_creation() {
    let unit = HybridReasonUnit::new(State::stable("Dog"));

    assert_eq!(unit.state().kind, StateKind::Stable);
    assert_eq!(unit.state().as_stable().unwrap().identity, "Dog");

    let serialized = serde_json::to_value(&unit).unwrap();
    assert_eq!(
        serialized
            .as_object()
            .unwrap()
            .keys()
            .cloned()
            .collect::<Vec<_>>(),
        vec!["state"]
    );
}

#[test]
fn hru_02_ambiguous_reason_unit_creation() {
    let unit = HybridReasonUnit::new(high_state());
    let ambiguous = unit.state().as_ambiguous().unwrap();

    assert_eq!(unit.state().kind, StateKind::Ambiguous);
    assert_eq!(ambiguous.candidates.len(), 3);
    assert_eq!(
        ambiguous
            .candidates
            .iter()
            .map(|candidate| candidate.probability)
            .collect::<Vec<_>>(),
        vec![0.45, 0.40, 0.15]
    );
}

#[test]
fn hru_03_low_ambiguity_real_resolution() {
    let mut runtime = HybridRuntime::new(HybridReasonUnit::new(low_state()));
    runtime.set_trace_test_id("HRU-03");

    let outcome = runtime.resolve_identity().unwrap();

    assert_eq!(
        outcome,
        ResolutionOutcome::Resolved(runtime.state_manager.current().as_stable().unwrap().clone())
    );
    assert_eq!(
        runtime.trace_logger.records()[0].selected_strategy,
        Some(StrategyKind::Real)
    );
    assert!(runtime.trace_logger.records()[0]
        .decision_reason
        .as_deref()
        .unwrap()
        .contains("minimum expected cost"));
    assert_required_trace_fields(&runtime);
}

#[test]
fn hru_04_medium_ambiguity_clarify_deferred() {
    let mut runtime = HybridRuntime::new(HybridReasonUnit::new(medium_state()));
    runtime.set_trace_test_id("HRU-04");

    let outcome = runtime.resolve_identity().unwrap();
    let requested_evidence = match outcome {
        ResolutionOutcome::Deferred {
            requested_evidence, ..
        } => requested_evidence,
        ResolutionOutcome::Resolved(_) => panic!("clarify must not fabricate a stable state"),
    };

    assert!(!requested_evidence.is_empty());
    assert_eq!(runtime.state_manager.current().kind, StateKind::Ambiguous);
    let trace = &runtime.trace_logger.records()[0];
    assert_eq!(trace.selected_strategy, Some(StrategyKind::Clarify));
    assert!(trace
        .resolution_outcome
        .as_deref()
        .unwrap()
        .contains("Deferred"));
    assert!(trace
        .resolution_outcome
        .as_deref()
        .unwrap()
        .contains("request evidence"));
    assert_required_trace_fields(&runtime);
}

#[test]
fn hru_05_high_ambiguity_complex_resolution() {
    let mut runtime = HybridRuntime::new(HybridReasonUnit::new(high_state()));
    runtime.set_trace_test_id("HRU-05");

    let observation = AmbiguityEvaluator
        .evaluate(runtime.state_manager.current().as_ambiguous().unwrap())
        .unwrap();
    assert_eq!(observation.evidence_conflict, 0.0);
    assert_eq!(observation.unsupported_evidence_ratio, 0.0);

    let outcome = runtime.resolve_identity().unwrap();

    assert!(matches!(outcome, ResolutionOutcome::Resolved(_)));
    assert_eq!(runtime.state_manager.current().kind, StateKind::Stable);
    let trace = &runtime.trace_logger.records()[0];
    assert_eq!(trace.selected_strategy, Some(StrategyKind::Complex));
    assert_eq!(trace.strategy_scores.len(), 3);
    assert_required_trace_fields(&runtime);
}

#[test]
fn hru_06_conflict_aware_decision() {
    let state = conflict_state();
    let observation = AmbiguityEvaluator
        .evaluate(state.as_ambiguous().unwrap())
        .unwrap();
    let strategies = [
        StrategyKind::Real,
        StrategyKind::Clarify,
        StrategyKind::Complex,
    ];
    let decision = DecisionEngine
        .decide(DecisionInput {
            ambiguity_observation: &observation,
            available_strategies: &strategies,
            risk_policy: &RiskPolicy::default(),
        })
        .unwrap();

    assert!((observation.evidence_conflict - 0.662).abs() < 0.01);
    assert_eq!(decision.strategy_scores.len(), 3);
    assert_eq!(decision.selected_strategy, StrategyKind::Clarify);
    assert_eq!(decision.alternative_strategies[0], StrategyKind::Complex);
    let gap = decision.strategy_scores[&decision.alternative_strategies[0]]
        - decision.strategy_scores[&decision.selected_strategy];
    assert!(gap > 0.0);

    let mut runtime = HybridRuntime::new(HybridReasonUnit::new(state));
    runtime.set_trace_test_id("HRU-06");
    runtime.resolve_identity().unwrap();
    let trace = &runtime.trace_logger.records()[0];
    assert_eq!(trace.selected_strategy, Some(StrategyKind::Clarify));
    assert_eq!(trace.alternative_strategies[0], StrategyKind::Complex);
    assert!((trace.selected_to_next_score_gap.unwrap() - gap).abs() < 1e-12);
    println!(
        "HRU-06 observation: conflict={:.6}, selected={:?}, scores={:?}, gap={:.6}",
        observation.evidence_conflict, decision.selected_strategy, decision.strategy_scores, gap
    );
    assert_required_trace_fields(&runtime);
}

#[test]
fn hru_07_stable_state_transition() {
    let mut runtime = HybridRuntime::new(HybridReasonUnit::new(State::stable("Dog")));
    runtime.set_trace_test_id("HRU-07");
    runtime.transition_engine.register("Dog", "IsA", "Mammal");

    let next = runtime.transition(Transition::new("IsA")).unwrap();

    assert_eq!(next.as_stable().unwrap().identity, "Mammal");
    assert_eq!(
        runtime
            .state_manager
            .current()
            .as_stable()
            .unwrap()
            .identity,
        "Mammal"
    );
    let trace = &runtime.trace_logger.records()[0];
    assert_eq!(trace.event_kind, TraceEventKind::Transition);
    assert_eq!(trace.transition_relation.as_deref(), Some("IsA"));
    assert_eq!(
        trace
            .next_state
            .as_ref()
            .unwrap()
            .as_stable()
            .unwrap()
            .identity,
        "Mammal"
    );
    assert_required_trace_fields(&runtime);
}

#[test]
fn hru_08_chained_transition() {
    let mut runtime = HybridRuntime::new(HybridReasonUnit::new(State::stable("Dog")));
    runtime.set_trace_test_id("HRU-08");
    runtime.transition_engine.register("Dog", "IsA", "Mammal");
    runtime
        .transition_engine
        .register("Mammal", "IsA", "Animal");

    runtime.transition(Transition::new("IsA")).unwrap();
    runtime.transition(Transition::new("IsA")).unwrap();

    assert_eq!(
        runtime
            .state_manager
            .current()
            .as_stable()
            .unwrap()
            .identity,
        "Animal"
    );
    assert_eq!(runtime.trace_logger.records().len(), 2);
    assert!(runtime
        .trace_logger
        .records()
        .iter()
        .all(|record| record.event_kind == TraceEventKind::Transition));
}

#[test]
fn hru_09_ambiguous_to_transition_pipeline() {
    let mut runtime = HybridRuntime::new(HybridReasonUnit::new(low_state()));
    runtime.set_trace_test_id("HRU-09");
    runtime.transition_engine.register("Dog", "IsA", "Mammal");

    runtime.resolve_identity().unwrap();
    runtime.transition(Transition::new("IsA")).unwrap();

    assert_eq!(
        runtime
            .state_manager
            .current()
            .as_stable()
            .unwrap()
            .identity,
        "Mammal"
    );
    assert_eq!(runtime.trace_logger.records().len(), 2);
    assert_eq!(
        runtime.trace_logger.records()[0].event_kind,
        TraceEventKind::Resolution
    );
    assert_eq!(
        runtime.trace_logger.records()[1].event_kind,
        TraceEventKind::Transition
    );
}

#[test]
fn hru_10_multiple_reason_unit_interaction() {
    let unit_a = HybridReasonUnit::new(State::stable("Dog"));
    let unit_b = HybridReasonUnit::new(State::stable("Mammal"));
    let mut runtime = HybridRuntime::new(unit_a);
    runtime.set_trace_test_id("HRU-10");
    runtime.state_manager.register_unit("unit_b", unit_b);

    let target_identity = runtime
        .state_manager
        .unit_named("unit_b")
        .unwrap()
        .state()
        .as_stable()
        .unwrap()
        .identity
        .clone();
    runtime
        .transition_engine
        .register("Dog", "IsA", target_identity);
    runtime.transition(Transition::new("IsA")).unwrap();

    assert_eq!(runtime.state_manager.unit_count(), 2);
    assert_eq!(
        runtime
            .state_manager
            .current()
            .as_stable()
            .unwrap()
            .identity,
        "Mammal"
    );
    assert_eq!(
        runtime
            .state_manager
            .unit_named("unit_b")
            .unwrap()
            .state()
            .as_stable()
            .unwrap()
            .identity,
        "Mammal"
    );
    assert_eq!(
        runtime.trace_logger.records()[0]
            .transition_relation
            .as_deref(),
        Some("IsA")
    );
}
