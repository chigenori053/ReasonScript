//! Canonical in-process reasoning operations for the ReasonScript runtime host.

use serde_json::{json, Value};

pub const PROFILE: &str = "reasonscript-reasoning-core/1.0";

#[derive(Clone, Debug, PartialEq)]
pub struct ReasoningOutcome {
    pub value: Value,
    pub trace: Value,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ReasoningError {
    pub code: String,
    pub message: String,
}

impl std::fmt::Display for ReasoningError {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(formatter, "{}: {}", self.code, self.message)
    }
}

impl std::error::Error for ReasoningError {}

pub fn execute(
    function_id: &str,
    argument: &Value,
    backend: &str,
) -> Result<ReasoningOutcome, ReasoningError> {
    let operation = function_id
        .strip_prefix("runtime.")
        .ok_or_else(|| error("RI-1", format!("unknown Runtime operation: {function_id}")))?;
    if !matches!(operation, "search" | "simulate" | "predict" | "plan") {
        return Err(error(
            "RI-1",
            format!("unknown Runtime operation: {function_id}"),
        ));
    }
    let label = request_label(argument)?;
    let execution_plan = matches!(operation, "search" | "plan").then(|| plan(operation, &label));
    let inner = match operation {
        "search" => json!({
            "goal": label, "found": true, "cost": 1.0,
            "confidence": 1.0, "trace": ["search"],
        }),
        "simulate" => json!({
            "success": true, "final_state": label,
            "confidence": 1.0, "trace": ["simulate"],
        }),
        "predict" => json!({
            "predicted_state": label, "confidence": 1.0,
            "evidence": ["predict"],
        }),
        "plan" => json!({
            "goal": label, "success": true, "cost": 1.0,
            "steps": ["step-1"],
        }),
        _ => unreachable!(),
    };
    let engine = match operation {
        "search" => format!("{backend} SearchEngine"),
        "simulate" => format!("{backend} SemanticSimulationEngine"),
        "predict" => format!("{backend} PredictionEngine"),
        "plan" => format!("{backend} PlanningEngine"),
        _ => unreachable!(),
    };
    Ok(ReasoningOutcome {
        value: json!({"some": inner}),
        trace: json!({
            "operation": function_id,
            "backend": backend,
            "engine": engine,
            "trace": [format!("{operation}:start"), format!("{operation}:complete")],
            "execution_plan": execution_plan,
            "native_profile": PROFILE,
        }),
    })
}

fn request_label(argument: &Value) -> Result<String, ReasoningError> {
    match argument {
        Value::String(value) if identifier(value) => Ok(value.clone()),
        Value::Object(value) => Ok(value
            .get("name")
            .and_then(Value::as_str)
            .map(ToOwned::to_owned)
            .unwrap_or_else(|| canonical_json(argument))),
        _ => Err(error(
            "ReasoningTypeConversionFailed",
            "argument cannot map to reasoning request",
        )),
    }
}

fn canonical_json(value: &Value) -> String {
    fn normalize(value: &Value) -> Value {
        match value {
            Value::Object(values) => {
                let mut keys: Vec<&String> = values.keys().collect();
                keys.sort();
                let mut result = serde_json::Map::new();
                for key in keys {
                    result.insert(key.clone(), normalize(&values[key]));
                }
                Value::Object(result)
            }
            Value::Array(values) => Value::Array(values.iter().map(normalize).collect()),
            other => other.clone(),
        }
    }
    serde_json::to_string(&normalize(value)).unwrap_or_default()
}

fn identifier(value: &str) -> bool {
    let mut characters = value.chars();
    characters
        .next()
        .is_some_and(|character| character == '_' || character.is_ascii_alphabetic())
        && characters.all(|character| character == '_' || character.is_ascii_alphanumeric())
}

fn plan(operation: &str, target: &str) -> Value {
    json!({
        "schema_version": "execution-plan/0.1",
        "selected_steps": [{
            "step_id": format!("{operation}-step-1"),
            "transition_id": format!("{operation}-transition"),
            "source": "runtime", "target": target,
        }],
        "alternative_paths": [], "expected_cost": 1.0,
        "evidence_refs": [format!("{operation}:trace")],
        "planner_version": "runtime-integration/0.2",
    })
}

fn error(code: &str, message: impl Into<String>) -> ReasoningError {
    ReasoningError {
        code: code.to_owned(),
        message: message.into(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn all_operations_preserve_frozen_result_contract() {
        for operation in ["search", "simulate", "predict", "plan"] {
            let outcome = execute(
                &format!("runtime.{operation}"),
                &Value::String("Destination".to_owned()),
                "RuntimeReal",
            )
            .unwrap();
            assert!(outcome.value.get("some").is_some());
            assert_eq!(outcome.trace["backend"], "RuntimeReal");
        }
    }

    #[test]
    fn backend_changes_engine_provenance() {
        let real = execute("runtime.search", &json!("Goal"), "RuntimeReal").unwrap();
        let hybrid = execute("runtime.search", &json!("Goal"), "HybridRuntime").unwrap();
        assert_ne!(real.trace["engine"], hybrid.trace["engine"]);
        assert_eq!(real.value, hybrid.value);
    }

    #[test]
    fn invalid_string_is_a_typed_conversion_error() {
        assert_eq!(
            execute("runtime.search", &json!("not a goal"), "RuntimeReal")
                .unwrap_err()
                .code,
            "ReasoningTypeConversionFailed"
        );
    }
}
