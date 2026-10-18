//! Decode one request into fresh VM values using the compiled, typed input layout.
use crate::value::{StructValue, Value};
use crate::{Program, RuntimeError};
use std::{cell::RefCell, collections::HashMap, rc::Rc};
use serde_json::Value as Json;

fn error(message: impl Into<String>) -> RuntimeError { RuntimeError::new("RTH-INPUT-001", message) }

pub fn arguments(program: &Program, entry: &str, input: &Json) -> Result<(String, HashMap<String, Value>), RuntimeError> {
    let abi = program.input_abi.as_ref().ok_or_else(|| error("program has no typed input ABI"))?;
    if abi["version"] != "reasonscript-input/1.0" { return Err(error("unsupported input ABI version")); }
    let entries = abi["entries"].as_object().ok_or_else(|| error("invalid entry layouts"))?;
    let matches: Vec<_> = entries.keys().filter(|id| id.as_str() == entry || id.strip_prefix("fn.") == Some(entry) || id.rsplit("::").next() == Some(entry)).collect();
    if matches.len() != 1 { return Err(error("entry must identify exactly one public typed function")); }
    let id = matches[0];
    let params = entries[id]["parameters"].as_object().ok_or_else(|| error("invalid parameter layout"))?;
    let values = input.as_object().ok_or_else(|| error("inputs must be a named JSON object"))?;
    if params.len() != values.len() || params.keys().any(|name| !values.contains_key(name)) { return Err(error("missing or unexpected input arguments")); }
    let mut budget = 100_000usize;
    let mut result = HashMap::new();
    for (name, ty) in params {
        result.insert(name.clone(), decode(&values[name], ty, &abi["structs"], 0, &mut budget)?);
    }
    Ok((id.clone(), result))
}

fn decode(value: &Json, ty: &Json, structs: &Json, depth: usize, budget: &mut usize) -> Result<Value, RuntimeError> {
    if depth > 64 || *budget == 0 { return Err(error("input nesting or element budget exceeded")); }
    *budget -= 1;
    match ty.as_str() {
        Some("Int") => return value.as_i64().map(Value::Int).ok_or_else(|| error("expected signed 64-bit Int")),
        Some("Float") => return value.as_f64().filter(|n| n.is_finite()).map(Value::Float).ok_or_else(|| error("expected finite Float")),
        Some("String") => return value.as_str().map(|s| Value::String(Rc::from(s))).ok_or_else(|| error("expected String")),
        Some("Bool") => return value.as_bool().map(Value::Bool).ok_or_else(|| error("expected Bool")),
        Some("Null") if value.is_null() => return Ok(Value::Null),
        _ => {}
    }
    if let Some(element) = ty.get("array") {
        let items = value.as_array().ok_or_else(|| error("expected Array"))?;
        if items.len() > *budget { return Err(error("input element budget exceeded")); }
        let items = items.iter().map(|v| decode(v, element, structs, depth+1, budget)).collect::<Result<Vec<_>,_>>()?;
        return Ok(Value::Array(Rc::new(RefCell::new(items))));
    }
    if let Some(types) = ty.get("tuple").and_then(Json::as_array) {
        let items = value.as_array().filter(|v| v.len() == types.len()).ok_or_else(|| error("tuple length mismatch"))?;
        let items = items.iter().zip(types).map(|(v,t)| decode(v,t,structs,depth+1,budget)).collect::<Result<Vec<_>,_>>()?;
        return Ok(Value::Array(Rc::new(RefCell::new(items))));
    }
    if let Some(inner) = ty.get("optional") {
        return if value.is_null() { Ok(Value::Optional(None)) } else { Ok(Value::Optional(Some(Box::new(decode(value, inner, structs, depth+1, budget)?)))) };
    }
    if let Some(name) = ty.get("struct").and_then(Json::as_str) {
        let spec = structs.get(name).ok_or_else(|| error("unknown struct input layout"))?;
        let fields = spec["fields"].as_object().ok_or_else(|| error("invalid struct layout"))?;
        let object = value.as_object().ok_or_else(|| error("expected Struct object"))?;
        if object.len() != fields.len() || fields.keys().any(|k| !object.contains_key(k)) { return Err(error(format!("missing or unexpected fields for {name}"))); }
        let fields = fields.iter().map(|(k,t)| Ok((k.clone(),decode(&object[k],t,structs,depth+1,budget)?))).collect::<Result<HashMap<_,_>,RuntimeError>>()?;
        return Ok(Value::Struct(Rc::new(StructValue { type_name: spec["type_name"].as_str().ok_or_else(|| error("invalid struct type name"))?.into(), fields: RefCell::new(fields) })));
    }
    Err(error("unsupported input type"))
}
