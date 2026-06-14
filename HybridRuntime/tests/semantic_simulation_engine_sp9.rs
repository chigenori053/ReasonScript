use reasonscript_hybrid_runtime::semantic_planning::PlanStep;
use reasonscript_hybrid_runtime::{
    SemanticPlan, SemanticPlanningEngine, SemanticPlanningError, SemanticSimulationEngine,
    SemanticSimulationError, SemanticTransformationEngine, SemanticType, SemanticTypeId,
    SemanticTypeRegistry, SimulationResult, SimulationResultIrNode, SimulationTraceIrNode,
    SIMULATION_RESULT_NODE, SIMULATION_TRACE_NODE,
};

fn id(value: &str) -> SemanticTypeId {
    SemanticTypeId::from(value)
}

fn simulation_engine() -> SemanticSimulationEngine {
    let mut types = SemanticTypeRegistry::new();
    types.register_type(SemanticType::root("Entity")).unwrap();
    types
        .register_type(SemanticType::child("LivingThing", "Entity"))
        .unwrap();
    types
        .register_type(SemanticType::child("Animal", "LivingThing"))
        .unwrap();
    types
        .register_type(SemanticType::child("Dog", "Animal"))
        .unwrap();
    types
        .register_type(SemanticType::child("Cat", "Animal"))
        .unwrap();
    types
        .register_type(SemanticType::child("Vehicle", "Entity"))
        .unwrap();

    SemanticSimulationEngine::new(
        SemanticPlanningEngine::new(SemanticTransformationEngine::new(types.clone())),
        SemanticTransformationEngine::new(types),
    )
}

#[test]
fn ssi_001_identity_simulation() {
    let plan = simulation_engine()
        .planning_engine()
        .shortest_plan(&id("Dog"), &id("Dog"))
        .unwrap();
    let result = simulation_engine().simulate(&plan).unwrap();

    assert_eq!(result.final_state, id("Dog"));
    assert_eq!(result.distance, 0);
    assert_eq!(result.trace.states, vec![id("Dog")]);
    assert!(result.reachable);
}

#[test]
fn ssi_002_reachable_simulation() {
    let engine = simulation_engine();
    let plan = engine
        .planning_engine()
        .shortest_plan(&id("Dog"), &id("Entity"))
        .unwrap();
    let result = engine.simulate(&plan).unwrap();

    assert_eq!(result.initial_state, id("Dog"));
    assert_eq!(result.final_state, id("Entity"));
    assert_eq!(result.distance, 3);
    assert!(result.reachable);
}

#[test]
fn ssi_003_goal_simulation() {
    let result = simulation_engine()
        .simulate_goal(&id("Dog"), &id("Entity"))
        .unwrap();

    assert_eq!(result.final_state, id("Entity"));
}

#[test]
fn ssi_004_predict() {
    assert_eq!(
        simulation_engine()
            .predict(&id("Dog"), &id("Entity"))
            .unwrap(),
        id("Entity")
    );
}

#[test]
fn ssi_005_trace_validation() {
    let result = simulation_engine()
        .simulate_goal(&id("Dog"), &id("Entity"))
        .unwrap();

    assert_eq!(
        result.trace.states,
        vec![id("Dog"), id("Animal"), id("LivingThing"), id("Entity")]
    );
}

#[test]
fn ssi_006_not_reachable() {
    assert!(matches!(
        simulation_engine().simulate_goal(&id("Animal"), &id("Vehicle")),
        Err(SemanticSimulationError::Planning(
            SemanticPlanningError::Unreachable { .. }
        ))
    ));
}

#[test]
fn ssi_007_invalid_plan() {
    let invalid = SemanticPlan {
        start: id("Dog"),
        goal: id("Entity"),
        steps: vec![PlanStep {
            source: id("Animal"),
            target: id("Entity"),
        }],
        distance: 1,
    };

    assert!(matches!(
        simulation_engine().simulate(&invalid),
        Err(SemanticSimulationError::Planning(
            SemanticPlanningError::InvalidPlan { .. }
        ))
    ));
}

#[test]
fn ssi_008_ir_serialization() {
    let result = simulation_engine()
        .simulate_goal(&id("Dog"), &id("Entity"))
        .unwrap();
    let trace_ir = SimulationTraceIrNode::from(&result.trace);
    let result_ir = SimulationResultIrNode::from(&result);

    assert_eq!(
        serde_json::to_value(&trace_ir).unwrap(),
        serde_json::json!({
            "node_type": SIMULATION_TRACE_NODE,
            "states": ["Dog", "Animal", "LivingThing", "Entity"]
        })
    );
    assert_eq!(
        serde_json::to_value(&result_ir).unwrap(),
        serde_json::json!({
            "node_type": SIMULATION_RESULT_NODE,
            "final_state": "Entity",
            "distance": 3,
            "reachable": true
        })
    );
}

#[test]
fn ssi_009_json_roundtrip() {
    let result = simulation_engine()
        .simulate_goal(&id("Dog"), &id("Entity"))
        .unwrap();
    let restored: SimulationResult =
        serde_json::from_str(&result.to_json_pretty().unwrap()).unwrap();
    let ir = SimulationResultIrNode::from(&result);
    let restored_ir: SimulationResultIrNode =
        serde_json::from_str(&serde_json::to_string(&ir).unwrap()).unwrap();

    assert_eq!(restored, result);
    assert_eq!(restored_ir, ir);
}

#[test]
fn ssi_010_determinism() {
    let engine = simulation_engine();
    let expected = engine.simulate_goal(&id("Dog"), &id("Entity")).unwrap();
    let expected_json = expected.to_json_pretty().unwrap();

    for _ in 0..100 {
        let actual = engine.simulate_goal(&id("Dog"), &id("Entity")).unwrap();
        assert_eq!(actual, expected);
        assert_eq!(actual.to_json_pretty().unwrap(), expected_json);
    }
}

#[test]
fn simulation_rejects_semantically_non_direct_steps() {
    let invalid = SemanticPlan {
        start: id("Dog"),
        goal: id("Entity"),
        steps: vec![PlanStep {
            source: id("Dog"),
            target: id("Entity"),
        }],
        distance: 1,
    };

    assert_eq!(
        simulation_engine().simulate(&invalid),
        Err(SemanticSimulationError::InvalidStep {
            source: "Dog".to_string(),
            target: "Entity".to_string(),
            distance: 3,
        })
    );
}

#[test]
fn simulation_supports_descendant_plans() {
    let result = simulation_engine()
        .simulate_goal(&id("Animal"), &id("Dog"))
        .unwrap();

    assert_eq!(result.final_state, id("Dog"));
    assert_eq!(result.trace.states, vec![id("Animal"), id("Dog")]);
    assert_eq!(result.distance, 1);
}

#[test]
fn prediction_propagates_unknown_type_errors() {
    assert!(matches!(
        simulation_engine().predict(&id("Unknown"), &id("Entity")),
        Err(SemanticSimulationError::Planning(
            SemanticPlanningError::Transformation(_)
        ))
    ));
}
