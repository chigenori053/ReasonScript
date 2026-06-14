use reasonscript_hybrid_runtime::semantic_planning::PlanStep;
use reasonscript_hybrid_runtime::{
    PlanningGoal, PlanningResult, PlanningResultIrNode, SemanticPlan, SemanticPlanIrNode,
    SemanticPlanningEngine, SemanticPlanningError, SemanticTransformationEngine, SemanticType,
    SemanticTypeError, SemanticTypeId, SemanticTypeRegistry, PLANNING_RESULT_NODE,
    SEMANTIC_PLAN_NODE,
};

fn id(value: &str) -> SemanticTypeId {
    SemanticTypeId::from(value)
}

fn planning_engine() -> SemanticPlanningEngine {
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

    SemanticPlanningEngine::new(SemanticTransformationEngine::new(types))
}

#[test]
fn spe_001_identity_plan() {
    let plan = planning_engine()
        .shortest_plan(&id("Dog"), &id("Dog"))
        .unwrap();

    assert_eq!(plan.start, id("Dog"));
    assert_eq!(plan.goal, id("Dog"));
    assert_eq!(plan.distance, 0);
    assert!(plan.steps.is_empty());
}

#[test]
fn spe_002_ancestor_plan() {
    let plan = planning_engine()
        .shortest_plan(&id("Dog"), &id("Entity"))
        .unwrap();

    assert_eq!(
        plan.steps,
        vec![
            PlanStep {
                source: id("Dog"),
                target: id("Animal"),
            },
            PlanStep {
                source: id("Animal"),
                target: id("LivingThing"),
            },
            PlanStep {
                source: id("LivingThing"),
                target: id("Entity"),
            },
        ]
    );
    assert_eq!(plan.distance, 3);
}

#[test]
fn spe_003_descendant_plan() {
    let plan = planning_engine()
        .shortest_plan(&id("Animal"), &id("Dog"))
        .unwrap();

    assert_eq!(
        plan.steps,
        vec![PlanStep {
            source: id("Animal"),
            target: id("Dog"),
        }]
    );
}

#[test]
fn spe_004_reachable() {
    assert!(planning_engine().reachable(&id("Dog"), &id("Animal")));
}

#[test]
fn spe_005_not_reachable() {
    let engine = planning_engine();

    assert!(!engine.reachable(&id("Animal"), &id("Vehicle")));
    assert!(engine
        .plan(&id("Animal"), &id("Vehicle"))
        .unwrap()
        .plans
        .is_empty());
}

#[test]
fn spe_006_shortest_plan() {
    let plan = planning_engine()
        .shortest_plan(&id("Dog"), &id("LivingThing"))
        .unwrap();

    assert_eq!(plan.distance, 2);
    assert_eq!(plan.steps.len(), 2);
}

#[test]
fn spe_007_plan_validation() {
    let valid = planning_engine()
        .shortest_plan(&id("Dog"), &id("Entity"))
        .unwrap();
    valid.validate().unwrap();

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
        invalid.validate(),
        Err(SemanticPlanningError::InvalidPlan { .. })
    ));
}

#[test]
fn spe_008_unknown_type() {
    let error = planning_engine()
        .plan(&id("Unknown"), &id("Entity"))
        .unwrap_err();

    assert!(matches!(
        error,
        SemanticPlanningError::Transformation(
            reasonscript_hybrid_runtime::SemanticTransformationError::TypeHierarchy(
                SemanticTypeError::TypeNotFound(ref type_id)
            )
        ) if type_id == "Unknown"
    ));
    assert!(!planning_engine().reachable(&id("Unknown"), &id("Entity")));
}

#[test]
fn spe_009_ir_serialization() {
    let result = planning_engine().plan(&id("Dog"), &id("Entity")).unwrap();
    let plan_ir = SemanticPlanIrNode::from(&result.plans[0]);
    let result_ir = PlanningResultIrNode::from(&result);

    assert_eq!(
        serde_json::to_value(&plan_ir).unwrap(),
        serde_json::json!({
            "node_type": SEMANTIC_PLAN_NODE,
            "start": "Dog",
            "goal": "Entity",
            "distance": 3
        })
    );
    assert_eq!(
        serde_json::to_value(&result_ir).unwrap(),
        serde_json::json!({
            "node_type": PLANNING_RESULT_NODE,
            "goal": "Entity",
            "plans": [{
                "node_type": SEMANTIC_PLAN_NODE,
                "start": "Dog",
                "goal": "Entity",
                "distance": 3
            }]
        })
    );

    let restored_plan: SemanticPlan =
        serde_json::from_str(&result.plans[0].to_json_pretty().unwrap()).unwrap();
    let restored_result: PlanningResult =
        serde_json::from_str(&result.to_json_pretty().unwrap()).unwrap();
    assert_eq!(restored_plan, result.plans[0]);
    assert_eq!(restored_result, result);
}

#[test]
fn spe_010_determinism() {
    let engine = planning_engine();
    let expected = engine.plan(&id("Dog"), &id("Entity")).unwrap();
    let expected_json = expected.to_json_pretty().unwrap();

    for _ in 0..100 {
        let actual = engine.plan(&id("Dog"), &id("Entity")).unwrap();
        assert_eq!(actual, expected);
        assert_eq!(actual.to_json_pretty().unwrap(), expected_json);
    }
}

#[test]
fn unreachable_shortest_plan_returns_error() {
    assert_eq!(
        planning_engine().shortest_plan(&id("Animal"), &id("Vehicle")),
        Err(SemanticPlanningError::Unreachable {
            current: "Animal".to_string(),
            goal: "Vehicle".to_string(),
        })
    );
}

#[test]
fn planning_result_preserves_goal_definition() {
    let result = planning_engine().plan(&id("Dog"), &id("Entity")).unwrap();

    assert_eq!(
        result.goal,
        PlanningGoal {
            target: id("Entity")
        }
    );
}

#[test]
fn validation_rejects_noncontiguous_and_wrong_distance_plans() {
    let noncontiguous = SemanticPlan {
        start: id("Dog"),
        goal: id("Entity"),
        steps: vec![
            PlanStep {
                source: id("Dog"),
                target: id("Animal"),
            },
            PlanStep {
                source: id("LivingThing"),
                target: id("Entity"),
            },
        ],
        distance: 2,
    };
    let wrong_distance = SemanticPlan {
        start: id("Dog"),
        goal: id("Animal"),
        steps: vec![PlanStep {
            source: id("Dog"),
            target: id("Animal"),
        }],
        distance: 2,
    };

    assert!(noncontiguous.validate().is_err());
    assert!(wrong_distance.validate().is_err());
}
