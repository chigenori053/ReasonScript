//! Console standard output API dispatch: Console.log, Console.info, Console.warn, Console.error, and print.
//!
//! RS-DXLI-07: ReasonScript native standard output.
//! - print, Console.log, Console.info -> stdout
//! - Console.warn, Console.error -> stderr
//! - Deterministic stringification across Python and Rust runtimes.

use std::cell::RefCell;
use std::collections::BTreeMap;
use serde::{Deserialize, Serialize};

use crate::value::Value;
use crate::vm::RuntimeError;

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ConsoleEvent {
    pub stream: String,
    pub level: String,
    pub message: String,
}

type VResult = Result<Value, RuntimeError>;

pub fn dispatch(
    function_id: &str,
    args: &[Value],
    events: &RefCell<Vec<ConsoleEvent>>,
) -> VResult {
    let (stream, level) = match function_id {
        "print" => ("stdout", "print"),
        "Console.log" => ("stdout", "log"),
        "Console.info" => ("stdout", "info"),
        "Console.warn" => ("stderr", "warn"),
        "Console.error" => ("stderr", "error"),
        _ => {
            return Err(RuntimeError::new(
                "CON-001",
                format!("unknown Console function: {function_id}"),
            ));
        }
    };

    let formatted_parts: Vec<String> = args.iter().map(format_console_value).collect();
    let line = formatted_parts.join(" ");

    events.borrow_mut().push(ConsoleEvent {
        stream: stream.to_string(),
        level: level.to_string(),
        message: line,
    });

    Ok(Value::Null)
}

pub fn format_console_value(value: &Value) -> String {
    match value {
        Value::Null => "null".to_string(),
        Value::Bool(b) => {
            if *b {
                "true".to_string()
            } else {
                "false".to_string()
            }
        }
        Value::Int(i) => i.to_string(),
        Value::Float(f) => {
            let text = format!("{f}");
            if text.contains('.') || text.contains('e') || text.contains("inf") {
                text
            } else {
                format!("{text}.0")
            }
        }
        Value::String(s) => s.to_string(),
        Value::Array(items) => {
            let parts: Vec<String> = items.borrow().iter().map(format_console_value).collect();
            format!("[{}]", parts.join(", "))
        }
        Value::Struct(s) => {
            // Sort keys alphabetically for determinism
            let fields = s.fields.borrow();
            let sorted: BTreeMap<&String, &Value> = fields.iter().collect();
            let parts: Vec<String> = sorted
                .into_iter()
                .map(|(k, v)| format!("{k}: {}", format_console_value(v)))
                .collect();
            format!("{{{}}}", parts.join(", "))
        }
        Value::Enum {
            enum_name,
            variant_name,
        } => format!("{enum_name}.{variant_name}"),
        Value::Optional(Some(inner)) => format!("Some({})", format_console_value(inner)),
        Value::Optional(None) => "None".to_string(),
        Value::Tensor(id) => format!("<tensor {id}>"),
        Value::ReasonObject(obj) => {
            format!("<reason_object {}>", obj.object.borrow().object_id.as_str())
        }
        Value::ReasonObjectSnapshot(snap) => {
            format!("<reason_object_snapshot {}>", snap.object.object_id.as_str())
        }
        Value::ReasonTransaction(_) => "<reason_transaction>".to_string(),
        Value::Json(j) => format!("{j}"),
    }
}
