//! Dispatches `string.*` IR calls: the Phase 2 "String標準ライブラリ"
//! minimal set (see `frontend/string/integration.py` for the full design
//! rationale -- extending `+` to strings would make the existing
//! numeric-only arithmetic type rule ambiguous, so this is a namespaced
//! function set instead).
//!
//! Every function is a pure transformation over `Value::String`/`Int`/
//! `Float`/`Array<String>` arguments -- no `TensorStore`, no persistent
//! state, matching `relation_dispatch`.

use std::rc::Rc;

use crate::value::Value;
use crate::vm::RuntimeError;

type VResult = Result<Value, RuntimeError>;

pub fn call(function_id: &str, mut args: Vec<Value>) -> VResult {
    let name = function_id.strip_prefix("string.").unwrap_or(function_id);
    let expected = match name {
        "concat" | "join" => 2,
        "length" | "from_int" | "from_float" => 1,
        "slice" => 3,
        _ => {
            return Err(RuntimeError::new(
                "STR-001",
                format!("unknown String function: {function_id}"),
            ))
        }
    };
    if args.len() != expected {
        return Err(RuntimeError::new(
            "STR-002",
            format!("String function argument count mismatch: {function_id} expects {expected}"),
        ));
    }
    match name {
        "concat" => {
            let b = as_string(&args.remove(1), function_id)?;
            let a = as_string(&args.remove(0), function_id)?;
            Ok(Value::String(Rc::from(format!("{a}{b}").as_str())))
        }
        "join" => {
            let values = as_string_array(&args.remove(1), function_id)?;
            let separator = as_string(&args.remove(0), function_id)?;
            Ok(Value::String(Rc::from(values.join(&separator).as_str())))
        }
        "length" => {
            let value = as_string(&args.remove(0), function_id)?;
            Ok(Value::Int(value.chars().count() as i64))
        }
        "from_int" => {
            let value = as_int(&args.remove(0), function_id)?;
            Ok(Value::String(Rc::from(value.to_string().as_str())))
        }
        "from_float" => {
            let value = as_float(&args.remove(0), function_id)?;
            Ok(Value::String(Rc::from(format_float(value).as_str())))
        }
        "slice" => {
            let end = as_int(&args.remove(2), function_id)?;
            let start = as_int(&args.remove(1), function_id)?;
            let value = as_string(&args.remove(0), function_id)?;
            let chars: Vec<char> = value.chars().collect();
            let length = chars.len() as i64;
            if start < 0 || end < start || end > length {
                return Err(RuntimeError::new(
                    "STR-004",
                    format!("string.slice bounds out of range: {start}..{end}"),
                ));
            }
            let sliced: String = chars[start as usize..end as usize].iter().collect();
            Ok(Value::String(Rc::from(sliced.as_str())))
        }
        _ => unreachable!("caller already matched name against this exact set"),
    }
}

/// Canonical `Float -> String` text, matched byte-for-byte by the Python
/// interpreter's `integrated_computation_runtime.format_float` for the
/// normal range (both sides use a shortest-round-trip digit algorithm
/// that agrees digit-for-digit; only extreme magnitudes, where Python
/// switches to scientific notation and Rust never does, are not
/// guaranteed to match -- see that function's docstring).
pub fn format_float(value: f64) -> String {
    if value.is_nan() {
        return "nan".to_string();
    }
    let text = format!("{value}");
    if text.contains('.') || text.contains('e') || text.contains("inf") {
        text
    } else {
        format!("{text}.0")
    }
}

fn as_string(value: &Value, function_id: &str) -> Result<String, RuntimeError> {
    match value {
        Value::String(value) => Ok(value.to_string()),
        other => Err(RuntimeError::new(
            "STR-003",
            format!(
                "{function_id} argument must be String, got {}",
                other.type_name()
            ),
        )),
    }
}

fn as_string_array(value: &Value, function_id: &str) -> Result<Vec<String>, RuntimeError> {
    match value {
        Value::Array(items) => items
            .borrow()
            .iter()
            .map(|item| as_string(item, function_id))
            .collect(),
        other => Err(RuntimeError::new(
            "STR-003",
            format!(
                "{function_id} second argument must be Array<String>, got {}",
                other.type_name()
            ),
        )),
    }
}

fn as_int(value: &Value, function_id: &str) -> Result<i64, RuntimeError> {
    match value {
        Value::Int(value) => Ok(*value),
        other => Err(RuntimeError::new(
            "STR-003",
            format!(
                "{function_id} argument must be Int, got {}",
                other.type_name()
            ),
        )),
    }
}

fn as_float(value: &Value, function_id: &str) -> Result<f64, RuntimeError> {
    match value {
        Value::Float(value) => Ok(*value),
        other => Err(RuntimeError::new(
            "STR-003",
            format!(
                "{function_id} argument must be Float, got {}",
                other.type_name()
            ),
        )),
    }
}
