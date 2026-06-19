use reasonscript_runtime_real::runtime_binding::{
    execute_runtime_operation, RuntimeConstraint, RuntimeExecutionPlan, RuntimeGoal,
    RuntimeOperation, RuntimeOperationKind, RuntimeReasonGraph, RuntimeResult, RuntimeState,
    RuntimeValue,
};
use reasonscript_runtime_real::runtime_binding::{
    PlanningEngine, PlanningRequest, PredictionEngine, PredictionRequest, RuntimeEngineRegistry,
    SearchEngine, SearchRequest, SimulationEngine, SimulationRequest,
};
use std::sync::Arc;

struct TypedEngine;

impl SearchEngine for TypedEngine {
    fn search(&self, request: SearchRequest) -> RuntimeResult {
        match request.value {
            RuntimeValue::GoalValue(goal) => {
                RuntimeResult::success(RuntimeValue::String(goal.name))
            }
            RuntimeValue::ReasonGraphValue(graph) => {
                RuntimeResult::success(RuntimeValue::Int(graph.nodes.len() as i64))
            }
            _ => RuntimeResult::failure("ReasoningTypeConversionFailed"),
        }
    }
}

impl SimulationEngine for TypedEngine {
    fn simulate(&self, request: SimulationRequest) -> RuntimeResult {
        match request.value {
            RuntimeValue::ExecutionPlanValue(plan) => {
                RuntimeResult::success(RuntimeValue::String(plan.schema_version))
            }
            _ => RuntimeResult::failure("ReasoningTypeConversionFailed"),
        }
    }
}

impl PredictionEngine for TypedEngine {
    fn predict(&self, request: PredictionRequest) -> RuntimeResult {
        match request.value {
            RuntimeValue::StateValue(state) => {
                RuntimeResult::success(RuntimeValue::String(state.id))
            }
            _ => RuntimeResult::failure("ReasoningTypeConversionFailed"),
        }
    }
}

impl PlanningEngine for TypedEngine {
    fn plan(&self, request: PlanningRequest) -> RuntimeResult {
        match request.value {
            RuntimeValue::GoalValue(goal) => {
                RuntimeResult::success(RuntimeValue::String(goal.name))
            }
            RuntimeValue::ConstraintValue(constraint) => {
                RuntimeResult::success(RuntimeValue::String(constraint.name))
            }
            _ => RuntimeResult::failure("ReasoningTypeConversionFailed"),
        }
    }
}

fn registry() -> RuntimeEngineRegistry {
    let engine = Arc::new(TypedEngine);
    RuntimeEngineRegistry::new()
        .with_search_engine(engine.clone())
        .with_simulation_engine(engine.clone())
        .with_prediction_engine(engine.clone())
        .with_planning_engine(engine)
}

#[test]
fn typed_reasoning_values_dispatch_to_expected_requests() {
    let cases = [
        (
            RuntimeOperationKind::SearchOperation,
            RuntimeValue::GoalValue(RuntimeGoal {
                name: "Destination".to_string(),
            }),
            "Destination",
        ),
        (
            RuntimeOperationKind::SimulationOperation,
            RuntimeValue::ExecutionPlanValue(RuntimeExecutionPlan {
                schema_version: "execution-plan/0.1".to_string(),
                selected_steps: vec![],
                expected_cost: 0.0,
            }),
            "execution-plan/0.1",
        ),
        (
            RuntimeOperationKind::PredictionOperation,
            RuntimeValue::StateValue(RuntimeState {
                id: "Dog".to_string(),
            }),
            "Dog",
        ),
        (
            RuntimeOperationKind::PlanningOperation,
            RuntimeValue::ConstraintValue(RuntimeConstraint {
                name: "MaxCost".to_string(),
            }),
            "MaxCost",
        ),
    ];

    for (kind, argument, expected) in cases {
        let result = execute_runtime_operation(&registry(), RuntimeOperation { kind, argument });
        assert_eq!(result.value, Some(RuntimeValue::String(expected.to_string())));
    }
}

#[test]
fn reason_graph_value_preserves_identity() {
    let graph = RuntimeValue::ReasonGraphValue(RuntimeReasonGraph {
        nodes: vec!["Dog".to_string()],
        edges: vec![],
    });
    let result = execute_runtime_operation(
        &registry(),
        RuntimeOperation {
            kind: RuntimeOperationKind::SearchOperation,
            argument: graph.clone(),
        },
    );

    assert_eq!(graph, RuntimeValue::ReasonGraphValue(RuntimeReasonGraph {
        nodes: vec!["Dog".to_string()],
        edges: vec![],
    }));
    assert_eq!(result.value, Some(RuntimeValue::Int(1)));
}
