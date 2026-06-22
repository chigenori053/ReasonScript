use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct InputState {
    pub state_id: String,
    pub state_type: String,
    pub value: Value,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct OutputEvent {
    pub output_id: String,
    pub source_state: String,
    pub projection: String,
    pub rendered_value: Value,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum ProjectionPolicy {
    Canonical,
}

impl ProjectionPolicy {
    pub fn as_str(&self) -> &'static str {
        match self {
            ProjectionPolicy::Canonical => "canonical",
        }
    }
}

#[derive(Debug, Clone, Default)]
pub struct RuntimeIo;

impl RuntimeIo {
    pub fn input(value: Value) -> InputState {
        InputState {
            state_id: "Input1".to_string(),
            state_type: "Input".to_string(),
            value,
        }
    }

    pub fn print_state(source_state: &str, state: &Value) -> OutputEvent {
        Self::project(source_state, state, ProjectionPolicy::Canonical)
    }

    pub fn project(
        source_state: &str,
        state: &Value,
        projection: ProjectionPolicy,
    ) -> OutputEvent {
        let rendered_value = canonical_state_projection(state);
        OutputEvent {
            output_id: deterministic_output_id(source_state, projection.as_str(), &rendered_value),
            source_state: source_state.to_string(),
            projection: projection.as_str().to_string(),
            rendered_value,
        }
    }
}

pub fn canonical_state_projection(state: &Value) -> Value {
    state.clone()
}

fn deterministic_output_id(
    source_state: &str,
    projection: &str,
    rendered_value: &Value,
) -> String {
    format!(
        "output:{}:{}:{}",
        source_state,
        projection,
        serde_json::to_string(rendered_value).unwrap_or_else(|_| "null".to_string())
    )
}

pub fn input_operation(value: Value) -> Value {
    json!({
        "operation": "input",
        "state": RuntimeIo::input(value),
    })
}

pub fn print_operation(source_state: &str, state: &Value) -> Value {
    json!({
        "operation": "print",
        "source_state": source_state,
        "output_event": RuntimeIo::print_state(source_state, state),
        "state_delta": null,
    })
}
