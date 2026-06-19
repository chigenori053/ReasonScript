use reasonscript_runtime_real::runtime_binding::{
    execute_runtime_operation, PlanningEngine, PlanningRequest, PredictionEngine,
    PredictionRequest, RuntimeEngineRegistry, RuntimeOperation, RuntimeOperationKind,
    RuntimeResult, RuntimeValue, SearchEngine, SearchRequest, SimulationEngine,
    SimulationRequest,
};
use std::sync::Arc;

struct Engine(&'static str);

impl SearchEngine for Engine {
    fn search(&self, request: SearchRequest) -> RuntimeResult {
        RuntimeResult::success(RuntimeValue::Array(vec![
            RuntimeValue::String(format!("{}:search", self.0)),
            request.value,
        ]))
    }
}

impl SimulationEngine for Engine {
    fn simulate(&self, request: SimulationRequest) -> RuntimeResult {
        RuntimeResult::success(RuntimeValue::Array(vec![
            RuntimeValue::String(format!("{}:simulate", self.0)),
            request.value,
        ]))
    }
}

impl PredictionEngine for Engine {
    fn predict(&self, request: PredictionRequest) -> RuntimeResult {
        RuntimeResult::success(RuntimeValue::Array(vec![
            RuntimeValue::String(format!("{}:predict", self.0)),
            request.value,
        ]))
    }
}

impl PlanningEngine for Engine {
    fn plan(&self, request: PlanningRequest) -> RuntimeResult {
        RuntimeResult::success(RuntimeValue::Array(vec![
            RuntimeValue::String(format!("{}:plan", self.0)),
            request.value,
        ]))
    }
}

fn registry() -> RuntimeEngineRegistry {
    let engine = Arc::new(Engine("RuntimeReal"));
    RuntimeEngineRegistry::new()
        .with_search_engine(engine.clone())
        .with_simulation_engine(engine.clone())
        .with_prediction_engine(engine.clone())
        .with_planning_engine(engine)
}

#[test]
fn registry_dispatches_all_runtime_operations_to_engines() {
    let operations = [
        RuntimeOperationKind::SearchOperation,
        RuntimeOperationKind::SimulationOperation,
        RuntimeOperationKind::PredictionOperation,
        RuntimeOperationKind::PlanningOperation,
    ];

    let results: Vec<_> = operations
        .into_iter()
        .map(|kind| {
            execute_runtime_operation(
                &registry(),
                RuntimeOperation {
                    kind,
                    argument: RuntimeValue::String("GoalA".to_string()),
                },
            )
        })
        .collect();

    assert!(results.iter().all(|result| result.success));
    assert_eq!(
        results[0].value,
        Some(RuntimeValue::Array(vec![
            RuntimeValue::String("RuntimeReal:search".to_string()),
            RuntimeValue::String("GoalA".to_string())
        ]))
    );
}

#[test]
fn missing_engine_returns_diagnostic_failure() {
    let result = execute_runtime_operation(
        &RuntimeEngineRegistry::new(),
        RuntimeOperation {
            kind: RuntimeOperationKind::SearchOperation,
            argument: RuntimeValue::String("GoalA".to_string()),
        },
    );

    assert!(!result.success);
    assert!(result.diagnostics[0].contains("RI2-2"));
    assert_eq!(
        result.into_language_optional(),
        RuntimeValue::Optional(Box::new(None))
    );
}
