use reasonscript_runtime_real::runtime_binding::{
    execute_runtime_operation, RuntimeOperation, RuntimeOperationExecutor, RuntimeOperationKind,
    RuntimeResult, RuntimeValue,
};

struct DeterministicExecutor;

impl RuntimeOperationExecutor for DeterministicExecutor {
    fn search(&self, request: RuntimeValue) -> RuntimeResult {
        RuntimeResult::success(RuntimeValue::Array(vec![
            RuntimeValue::String("search".to_string()),
            request,
        ]))
    }

    fn simulate(&self, request: RuntimeValue) -> RuntimeResult {
        RuntimeResult::success(RuntimeValue::Array(vec![
            RuntimeValue::String("simulate".to_string()),
            request,
        ]))
    }

    fn predict(&self, request: RuntimeValue) -> RuntimeResult {
        RuntimeResult::success(RuntimeValue::Array(vec![
            RuntimeValue::String("predict".to_string()),
            request,
        ]))
    }

    fn plan(&self, request: RuntimeValue) -> RuntimeResult {
        RuntimeResult::success(RuntimeValue::Array(vec![
            RuntimeValue::String("plan".to_string()),
            request,
        ]))
    }
}

#[test]
fn runtime_operation_dispatch_is_deterministic() {
    let executor = DeterministicExecutor;
    let operation = RuntimeOperation {
        kind: RuntimeOperationKind::SearchOperation,
        argument: RuntimeValue::String("GoalA".to_string()),
    };

    let first = execute_runtime_operation(&executor, operation.clone());
    let second = execute_runtime_operation(&executor, operation);

    assert_eq!(first, second);
    assert!(first.success);
}

#[test]
fn runtime_result_maps_to_optional_language_value() {
    let success = RuntimeResult::success(RuntimeValue::Bool(true)).into_language_optional();
    let failure = RuntimeResult::failure("runtime failed").into_language_optional();

    assert_eq!(
        success,
        RuntimeValue::Optional(Box::new(Some(RuntimeValue::Bool(true))))
    );
    assert_eq!(failure, RuntimeValue::Optional(Box::new(None)));
}
