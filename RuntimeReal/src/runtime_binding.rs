use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub enum RuntimeValue {
    Bool(bool),
    Int(i64),
    Float(f64),
    String(String),
    Struct(RuntimeStruct),
    Enum(RuntimeEnum),
    Array(Vec<RuntimeValue>),
    Optional(Box<Option<RuntimeValue>>),
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct RuntimeStruct {
    pub fields: BTreeMap<String, RuntimeValue>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct RuntimeEnum {
    pub enum_name: String,
    pub value_name: String,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct RuntimeResult {
    pub success: bool,
    pub value: Option<RuntimeValue>,
    pub diagnostics: Vec<String>,
}

impl RuntimeResult {
    pub fn success(value: RuntimeValue) -> Self {
        Self {
            success: true,
            value: Some(value),
            diagnostics: Vec::new(),
        }
    }

    pub fn failure(diagnostic: impl Into<String>) -> Self {
        Self {
            success: false,
            value: None,
            diagnostics: vec![diagnostic.into()],
        }
    }

    pub fn into_language_optional(self) -> RuntimeValue {
        if self.success {
            RuntimeValue::Optional(Box::new(self.value))
        } else {
            RuntimeValue::Optional(Box::new(None))
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum RuntimeOperationKind {
    SearchOperation,
    SimulationOperation,
    PredictionOperation,
    PlanningOperation,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct RuntimeOperation {
    pub kind: RuntimeOperationKind,
    pub argument: RuntimeValue,
}

pub trait RuntimeOperationExecutor {
    fn search(&self, request: RuntimeValue) -> RuntimeResult;
    fn simulate(&self, request: RuntimeValue) -> RuntimeResult;
    fn predict(&self, request: RuntimeValue) -> RuntimeResult;
    fn plan(&self, request: RuntimeValue) -> RuntimeResult;
}

pub fn execute_runtime_operation<E: RuntimeOperationExecutor>(
    executor: &E,
    operation: RuntimeOperation,
) -> RuntimeResult {
    match operation.kind {
        RuntimeOperationKind::SearchOperation => executor.search(operation.argument),
        RuntimeOperationKind::SimulationOperation => executor.simulate(operation.argument),
        RuntimeOperationKind::PredictionOperation => executor.predict(operation.argument),
        RuntimeOperationKind::PlanningOperation => executor.plan(operation.argument),
    }
}
