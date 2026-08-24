//! Dispatches `relation.*` IR calls: the Phase 8 "relational algebra
//! core" (see `frontend/relation/integration.py` for the full design
//! rationale, including why `join`/`project` are NOT implemented here).
//!
//! Unlike `tensor_dispatch`/`optimizer_dispatch`, this module needs no
//! `TensorStore` -- every `relation.*` function is a pure read over an
//! `Array<Struct>` `Value`, reusing the same `Value` equality/ordering
//! `vm::eval_comparison` already implements for `==`/`<`/... expressions,
//! so a field comparison behaves identically to a plain comparison
//! expression written directly against two field-access reads.

use std::cmp::Ordering;

use crate::value::Value;
use crate::vm::{eval_comparison, RuntimeError};

type VResult = Result<Value, RuntimeError>;

pub fn call(function_id: &str, args: Vec<Value>) -> VResult {
    let name = function_id.strip_prefix("relation.").unwrap_or(function_id);
    let expected = match name {
        "filter_eq" | "filter_ne" | "filter_gt" | "filter_gte" | "filter_lt" | "filter_lte" => 3,
        "count" => 1,
        "distinct_by" => 2,
        "sort_by" => 3,
        _ => {
            return Err(RuntimeError::new(
                "REL-001",
                format!("unknown Relation function: {function_id}"),
            ))
        }
    };
    if args.len() != expected {
        return Err(RuntimeError::new(
            "REL-002",
            format!("Relation function argument count mismatch: {function_id} expects {expected}"),
        ));
    }
    match name {
        "count" => count(args),
        "distinct_by" => distinct_by(args),
        "sort_by" => sort_by(args),
        comparison_name => filter_compare(comparison_name, args),
    }
}

fn rows(value: Value) -> Result<Vec<Value>, RuntimeError> {
    match value {
        Value::Array(items) => {
            let items = items.borrow();
            for item in items.iter() {
                if !matches!(item, Value::Struct(_)) {
                    return Err(RuntimeError::new(
                        "REL-004",
                        "Relation function requires Array<Struct>",
                    ));
                }
            }
            Ok(items.clone())
        }
        other => Err(RuntimeError::new(
            "REL-004",
            format!("Relation function requires Array<Struct>, got Array of {}", other.type_name()),
        )),
    }
}

fn field(row: &Value, name: &str) -> Result<Value, RuntimeError> {
    match row {
        Value::Struct(struct_value) => struct_value.fields.borrow().get(name).cloned().ok_or_else(|| {
            RuntimeError::new(
                "REL-005",
                format!("unknown field {name} on {}", struct_value.type_name),
            )
        }),
        other => Err(RuntimeError::new(
            "REL-005",
            format!("expected a Struct row, got {}", other.type_name()),
        )),
    }
}

fn as_string(value: &Value) -> Result<String, RuntimeError> {
    match value {
        Value::String(value) => Ok(value.to_string()),
        other => Err(RuntimeError::new(
            "REL-003",
            format!("Relation field name must be a String, got {}", other.type_name()),
        )),
    }
}

fn count(mut args: Vec<Value>) -> VResult {
    let rows = rows(args.remove(0))?;
    Ok(Value::Int(rows.len() as i64))
}

fn filter_compare(comparison_name: &str, mut args: Vec<Value>) -> VResult {
    let operator = match comparison_name {
        "filter_eq" => "Equal",
        "filter_ne" => "NotEqual",
        "filter_gt" => "GreaterThan",
        "filter_gte" => "GreaterThanOrEqual",
        "filter_lt" => "LessThan",
        "filter_lte" => "LessThanOrEqual",
        _ => unreachable!("caller already matched comparison_name against this exact set"),
    };
    let target_value = args.remove(2);
    let field_name = as_string(&args.remove(1))?;
    let rows = rows(args.remove(0))?;
    let mut kept = Vec::new();
    for row in rows {
        let field_value = field(&row, &field_name)?;
        let matched = match eval_comparison(operator, field_value, target_value.clone()) {
            Ok(Value::Bool(value)) => value,
            Ok(_) => unreachable!("eval_comparison always returns Bool"),
            Err(error) => {
                return Err(RuntimeError::new(
                    "REL-006",
                    format!("Relation comparison is undefined: {}", error.message),
                ))
            }
        };
        if matched {
            kept.push(row);
        }
    }
    Ok(Value::Array(std::rc::Rc::new(std::cell::RefCell::new(kept))))
}

fn distinct_by(mut args: Vec<Value>) -> VResult {
    let field_name = as_string(&args.remove(1))?;
    let rows = rows(args.remove(0))?;
    let mut seen: Vec<Value> = Vec::new();
    let mut kept = Vec::new();
    for row in rows {
        let key = field(&row, &field_name)?;
        if !seen.iter().any(|existing| *existing == key) {
            seen.push(key);
            kept.push(row);
        }
    }
    Ok(Value::Array(std::rc::Rc::new(std::cell::RefCell::new(kept))))
}

fn sort_by(mut args: Vec<Value>) -> VResult {
    let descending = match args.remove(2) {
        Value::Bool(value) => value,
        other => {
            return Err(RuntimeError::new(
                "REL-007",
                format!("Relation sort_by descending must be Bool, got {}", other.type_name()),
            ))
        }
    };
    let field_name = as_string(&args.remove(1))?;
    let mut rows = rows(args.remove(0))?;
    let mut sort_error: Option<RuntimeError> = None;
    rows.sort_by(|left, right| {
        if sort_error.is_some() {
            return Ordering::Equal;
        }
        let left_field = match field(left, &field_name) {
            Ok(value) => value,
            Err(error) => {
                sort_error = Some(error);
                return Ordering::Equal;
            }
        };
        let right_field = match field(right, &field_name) {
            Ok(value) => value,
            Err(error) => {
                sort_error = Some(error);
                return Ordering::Equal;
            }
        };
        // Derived from `<` alone (two comparisons), matching Python's
        // `sorted()` -- which also only ever calls `__lt__` on the
        // extracted keys -- rather than assuming a 3-way comparator: a
        // naive "not less-than => greater" would report Greater for two
        // *equal* fields in both directions, an inconsistent ordering
        // (`compare(a, b) == Greater` while `compare(b, a) == Greater`
        // too) that a real 3-way comparator must not produce.
        match (
            eval_comparison("LessThan", left_field.clone(), right_field.clone()),
            eval_comparison("LessThan", right_field, left_field),
        ) {
            (Ok(Value::Bool(true)), _) => Ordering::Less,
            (_, Ok(Value::Bool(true))) => Ordering::Greater,
            (Ok(Value::Bool(false)), Ok(Value::Bool(false))) => Ordering::Equal,
            (Err(error), _) | (_, Err(error)) => {
                sort_error = Some(RuntimeError::new(
                    "REL-006",
                    format!("Relation field is not orderable: {}", error.message),
                ));
                Ordering::Equal
            }
            _ => unreachable!("eval_comparison always returns Bool"),
        }
    });
    if let Some(error) = sort_error {
        return Err(error);
    }
    if descending {
        rows.reverse();
    }
    Ok(Value::Array(std::rc::Rc::new(std::cell::RefCell::new(rows))))
}
