use reasonscript_hybrid_runtime::{
    AmbiguityEvaluator, Candidate, DecisionEngine, DecisionInput, Evidence, HybridReasonUnit,
    HybridRuntime, ResolutionOutcome, RiskPolicy, State, StateKind, StateManager, StrategyKind,
    TraceLogger, TraceRecord, Transition,
};

fn candidate(identity: &str, probability: f64, semantic_vector: &[f64]) -> Candidate {
    Candidate::new(identity, probability, semantic_vector.to_vec())
}

fn low_ambiguity_state() -> State {
    State::ambiguous(
        vec![
            candidate("Dog", 0.95, &[0.99, 0.99, 0.96, 0.18]),
            candidate("Wolf", 0.03, &[0.99, 0.96, 0.08, 0.96]),
            candidate("Fox", 0.02, &[0.99, 0.58, 0.06, 0.94]),
        ],
        vec![
            Evidence::supported("Animal", vec![0.99, 0.99, 0.99]),
            Evidence::supported("Domestic", vec![0.96, 0.08, 0.06]),
        ],
    )
}

fn medium_ambiguity_state() -> State {
    State::ambiguous(
        vec![
            candidate("Dog", 0.60, &[0.99, 0.99, 0.96, 0.18]),
            candidate("Wolf", 0.35, &[0.99, 0.96, 0.08, 0.96]),
            candidate("Fox", 0.05, &[0.99, 0.58, 0.06, 0.94]),
        ],
        vec![Evidence::supported("Canine", vec![0.99, 0.96, 0.58])],
    )
}

fn high_ambiguity_state() -> State {
    State::ambiguous(
        vec![
            candidate("Dog", 0.45, &[0.99, 0.99, 0.96, 0.18]),
            candidate("Wolf", 0.40, &[0.99, 0.96, 0.08, 0.96]),
            candidate("Fox", 0.15, &[0.99, 0.58, 0.06, 0.94]),
        ],
        vec![
            Evidence::supported("Pet", vec![0.97, 0.05, 0.04]),
            Evidence::supported("Wild", vec![0.18, 0.96, 0.94]),
            Evidence::unsupported("UnmappedContext"),
        ],
    )
}

#[test]
fn hrt_01_hybrid_reason_unit_generation() {
    let unit = HybridReasonUnit::new(State::stable("Dog"));

    assert_eq!(unit.state().kind, StateKind::Stable);
    assert_eq!(unit.state().as_stable().unwrap().identity, "Dog");
}

#[test]
fn hrt_02_state_management() {
    let unit = HybridReasonUnit::new(State::stable("Dog"));
    let mut manager = StateManager::new(unit);

    manager.replace(medium_ambiguity_state());
    assert_eq!(manager.current().kind, StateKind::Ambiguous);
    assert_eq!(
        manager.current().as_ambiguous().unwrap().candidates.len(),
        3
    );
}

#[test]
fn hrt_03_ambiguity_observation() {
    let state = high_ambiguity_state();
    let observation = AmbiguityEvaluator
        .evaluate(state.as_ambiguous().unwrap())
        .unwrap();

    assert!(observation.candidate_entropy > 1.4);
    assert!(observation.normalized_entropy > 0.9);
    assert!(observation.effective_candidate_count > 2.7);
    assert!((observation.top_candidate_probability - 0.45).abs() < 1e-12);
    assert!((observation.top_two_margin - 0.05).abs() < 1e-12);
    assert!(observation.semantic_candidate_density > 0.5);
    assert!(observation.evidence_conflict > 0.5);
    assert!((observation.unsupported_evidence_ratio - (1.0 / 3.0)).abs() < 1e-12);
}

#[test]
fn hrt_04_decision_execution() {
    let evaluator = AmbiguityEvaluator;
    let engine = DecisionEngine;
    let policy = RiskPolicy::default();
    let strategies = [
        StrategyKind::Real,
        StrategyKind::Clarify,
        StrategyKind::Complex,
    ];

    let low = evaluator
        .evaluate(low_ambiguity_state().as_ambiguous().unwrap())
        .unwrap();
    let medium = evaluator
        .evaluate(medium_ambiguity_state().as_ambiguous().unwrap())
        .unwrap();
    let high = evaluator
        .evaluate(high_ambiguity_state().as_ambiguous().unwrap())
        .unwrap();

    let decide = |observation| {
        engine
            .decide(DecisionInput {
                ambiguity_observation: observation,
                available_strategies: &strategies,
                risk_policy: &policy,
            })
            .unwrap()
    };

    assert_eq!(decide(&low).selected_strategy, StrategyKind::Real);
    assert_eq!(decide(&medium).selected_strategy, StrategyKind::Clarify);
    assert_eq!(decide(&high).selected_strategy, StrategyKind::Complex);
}

#[test]
fn hrt_05_identity_resolution() {
    let mut real_runtime = HybridRuntime::new(HybridReasonUnit::new(low_ambiguity_state()));
    let real_outcome = real_runtime.resolve_identity().unwrap();

    assert_eq!(
        real_outcome,
        ResolutionOutcome::Resolved(
            real_runtime
                .state_manager
                .current()
                .as_stable()
                .unwrap()
                .clone()
        )
    );
    assert_eq!(
        real_runtime
            .state_manager
            .current()
            .as_stable()
            .unwrap()
            .identity,
        "Dog"
    );

    let mut clarify_runtime = HybridRuntime::new(HybridReasonUnit::new(medium_ambiguity_state()));
    let clarify_outcome = clarify_runtime.resolve_identity().unwrap();
    assert!(matches!(
        clarify_outcome,
        ResolutionOutcome::Deferred { .. }
    ));
    assert_eq!(
        clarify_runtime.state_manager.current().kind,
        StateKind::Ambiguous
    );

    let mut complex_runtime = HybridRuntime::new(HybridReasonUnit::new(high_ambiguity_state()));
    let complex_outcome = complex_runtime.resolve_identity().unwrap();
    assert!(matches!(complex_outcome, ResolutionOutcome::Resolved(_)));
    assert_eq!(
        complex_runtime
            .state_manager
            .current()
            .as_stable()
            .unwrap()
            .identity,
        "Dog"
    );
}

#[test]
fn hrt_06_state_transition() {
    let mut runtime = HybridRuntime::new(HybridReasonUnit::new(State::stable("Dog")));
    runtime.transition_engine.register("Dog", "IsA", "Mammal");
    runtime
        .transition_engine
        .register("Mammal", "IsA", "Animal");

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
}

#[test]
fn hrt_07_trace_output() {
    let mut runtime = HybridRuntime::new(HybridReasonUnit::new(low_ambiguity_state()));
    runtime.resolve_identity().unwrap();

    assert_eq!(runtime.trace_logger.records().len(), 1);
    let record = &runtime.trace_logger.records()[0];
    assert_eq!(record.selected_strategy, Some(StrategyKind::Real));
    assert_eq!(record.candidate_distribution.len(), 3);
    assert_eq!(record.strategy_scores.len(), 3);
    assert_eq!(record.policy_version, "hybrid-runtime-v0.2-default");
    assert!(!record.decision_reason.as_deref().unwrap().is_empty());

    let json = runtime.trace_logger.to_json_pretty().unwrap();
    assert!(json.contains("\"candidate_distribution\""));
    assert!(json.contains("\"ambiguity_observation\""));
    assert!(json.contains("\"selected_strategy\": \"Real\""));
    assert!(json.contains("\"policy_version\": \"hybrid-runtime-v0.2-default\""));
}

#[test]
fn trace_logger_accepts_explicit_records() {
    let observation = AmbiguityEvaluator
        .evaluate(low_ambiguity_state().as_ambiguous().unwrap())
        .unwrap();
    let decision = DecisionEngine
        .decide(DecisionInput {
            ambiguity_observation: &observation,
            available_strategies: &[StrategyKind::Real],
            risk_policy: &RiskPolicy::default(),
        })
        .unwrap();
    let outcome = ResolutionOutcome::Resolved(
        low_ambiguity_state()
            .as_ambiguous()
            .unwrap()
            .candidates
            .first()
            .map(|candidate| reasonscript_hybrid_runtime::StableState::new(&candidate.identity))
            .unwrap(),
    );
    let record = TraceRecord::resolution(
        low_ambiguity_state(),
        vec![("Dog".to_string(), 1.0)],
        observation,
        decision,
        &outcome,
        "test-policy",
        "test-evaluator",
    );
    let mut logger = TraceLogger::default();
    logger.record(record);

    assert_eq!(logger.records()[0].confidence, Some(1.0));
}
