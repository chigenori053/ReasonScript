use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use std::sync::Arc;

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
    GoalValue(RuntimeGoal),
    StateValue(RuntimeState),
    ConstraintValue(RuntimeConstraint),
    ReasonGraphValue(RuntimeReasonGraph),
    ExecutionPlanValue(RuntimeExecutionPlan),
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

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct RuntimeGoal {
    pub name: String,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct RuntimeState {
    pub id: String,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct RuntimeConstraint {
    pub name: String,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct RuntimeReasonGraph {
    pub nodes: Vec<String>,
    pub edges: Vec<String>,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct RuntimeExecutionPlan {
    pub schema_version: String,
    pub selected_steps: Vec<String>,
    pub expected_cost: f64,
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

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct SearchRequest {
    pub value: RuntimeValue,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct SimulationRequest {
    pub value: RuntimeValue,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct PredictionRequest {
    pub value: RuntimeValue,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct PlanningRequest {
    pub value: RuntimeValue,
}

pub trait SearchEngine: Send + Sync {
    fn search(&self, request: SearchRequest) -> RuntimeResult;
}

pub trait SimulationEngine: Send + Sync {
    fn simulate(&self, request: SimulationRequest) -> RuntimeResult;
}

pub trait PredictionEngine: Send + Sync {
    fn predict(&self, request: PredictionRequest) -> RuntimeResult;
}

pub trait PlanningEngine: Send + Sync {
    fn plan(&self, request: PlanningRequest) -> RuntimeResult;
}

#[derive(Clone, Default)]
pub struct RuntimeEngineRegistry {
    pub search_engine: Option<Arc<dyn SearchEngine>>,
    pub simulation_engine: Option<Arc<dyn SimulationEngine>>,
    pub prediction_engine: Option<Arc<dyn PredictionEngine>>,
    pub planning_engine: Option<Arc<dyn PlanningEngine>>,
}

impl RuntimeEngineRegistry {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn with_search_engine(mut self, engine: Arc<dyn SearchEngine>) -> Self {
        self.search_engine = Some(engine);
        self
    }

    pub fn with_simulation_engine(mut self, engine: Arc<dyn SimulationEngine>) -> Self {
        self.simulation_engine = Some(engine);
        self
    }

    pub fn with_prediction_engine(mut self, engine: Arc<dyn PredictionEngine>) -> Self {
        self.prediction_engine = Some(engine);
        self
    }

    pub fn with_planning_engine(mut self, engine: Arc<dyn PlanningEngine>) -> Self {
        self.planning_engine = Some(engine);
        self
    }
}

pub trait RuntimeOperationExecutor {
    fn search(&self, request: RuntimeValue) -> RuntimeResult;
    fn simulate(&self, request: RuntimeValue) -> RuntimeResult;
    fn predict(&self, request: RuntimeValue) -> RuntimeResult;
    fn plan(&self, request: RuntimeValue) -> RuntimeResult;
}

impl RuntimeOperationExecutor for RuntimeEngineRegistry {
    fn search(&self, request: RuntimeValue) -> RuntimeResult {
        match &self.search_engine {
            Some(engine) => engine.search(SearchRequest { value: request }),
            None => RuntimeResult::failure("RI2-2 Engine registry missing search engine"),
        }
    }

    fn simulate(&self, request: RuntimeValue) -> RuntimeResult {
        match &self.simulation_engine {
            Some(engine) => engine.simulate(SimulationRequest { value: request }),
            None => RuntimeResult::failure("RI2-2 Engine registry missing simulation engine"),
        }
    }

    fn predict(&self, request: RuntimeValue) -> RuntimeResult {
        match &self.prediction_engine {
            Some(engine) => engine.predict(PredictionRequest { value: request }),
            None => RuntimeResult::failure("RI2-2 Engine registry missing prediction engine"),
        }
    }

    fn plan(&self, request: RuntimeValue) -> RuntimeResult {
        match &self.planning_engine {
            Some(engine) => engine.plan(PlanningRequest { value: request }),
            None => RuntimeResult::failure("RI2-2 Engine registry missing planning engine"),
        }
    }
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
