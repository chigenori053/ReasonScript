//! Decode one request into fresh VM values using the compiled, typed input layout.
use crate::value::{StructValue, Value};
use crate::{Program, RuntimeError};
use serde_json::Value as Json;
use std::{cell::RefCell, collections::HashMap, rc::Rc};

pub const DEFAULT_MAX_INPUT_ELEMENTS: usize = 100_000;
pub const MAX_INPUT_ELEMENTS: usize = 10_000_000;
pub const MAX_INPUT_BYTES: usize = 1_073_741_824;

/// Admission bounds for typed values, separate from VM execution limits.
#[derive(Clone, Copy, Debug)]
pub struct InputLimits {
    pub max_elements: usize,
    pub max_bytes: Option<usize>,
}

impl Default for InputLimits {
    fn default() -> Self {
        Self {
            max_elements: DEFAULT_MAX_INPUT_ELEMENTS,
            max_bytes: None,
        }
    }
}

impl InputLimits {
    fn validate(self) -> Result<(), RuntimeError> {
        if self.max_elements == 0 || self.max_elements > MAX_INPUT_ELEMENTS {
            return Err(error("max_input_elements must be in 1..=10000000"));
        }
        if self
            .max_bytes
            .is_some_and(|n| n == 0 || n > MAX_INPUT_BYTES)
        {
            return Err(error("max_input_bytes must be in 1..=1073741824"));
        }
        Ok(())
    }
}

struct ByteBudget(usize);

impl std::io::Write for ByteBudget {
    fn write(&mut self, bytes: &[u8]) -> std::io::Result<usize> {
        if bytes.len() > self.0 {
            return Err(std::io::Error::other("input byte budget exceeded"));
        }
        self.0 -= bytes.len();
        Ok(bytes.len())
    }
    fn flush(&mut self) -> std::io::Result<()> {
        Ok(())
    }
}

// Walk borrowed JSON and its layout before allocating typed values, including
// the virtual Optional nodes charged by the existing decoder.
fn admit(
    value: &Json,
    ty: &Json,
    structs: &Json,
    depth: usize,
    remaining: &mut usize,
) -> Result<(), RuntimeError> {
    if depth > 64 || *remaining == 0 {
        return Err(error("input nesting or element budget exceeded"));
    }
    *remaining -= 1;
    if let Some(inner) = ty.get("optional") {
        if !value.is_null() {
            admit(value, inner, structs, depth + 1, remaining)?;
        }
    } else if let Some(items) = value.as_array() {
        if let Some(element) = ty.get("array") {
            if items.len() > *remaining {
                return Err(error("input element budget exceeded"));
            }
            for item in items {
                admit(item, element, structs, depth + 1, remaining)?;
            }
        } else if let Some(types) = ty.get("tuple").and_then(Json::as_array) {
            for (item, element) in items.iter().zip(types) {
                admit(item, element, structs, depth + 1, remaining)?;
            }
        }
    } else if let (Some(object), Some(name)) =
        (value.as_object(), ty.get("struct").and_then(Json::as_str))
    {
        if let Some(fields) = structs.get(name).and_then(|s| s["fields"].as_object()) {
            for (key, element) in fields {
                if let Some(item) = object.get(key) {
                    admit(item, element, structs, depth + 1, remaining)?;
                }
            }
        }
    }
    Ok(())
}

fn error(message: impl Into<String>) -> RuntimeError {
    RuntimeError::new("RTH-INPUT-001", message)
}

pub fn arguments(
    program: &Program,
    entry: &str,
    input: &Json,
) -> Result<(String, HashMap<String, Value>), RuntimeError> {
    arguments_with_limits(program, entry, input, InputLimits::default())
}

pub fn arguments_with_limits(
    program: &Program,
    entry: &str,
    input: &Json,
    limits: InputLimits,
) -> Result<(String, HashMap<String, Value>), RuntimeError> {
    limits.validate()?;
    let abi = program
        .input_abi
        .as_ref()
        .ok_or_else(|| error("program has no typed input ABI"))?;
    if abi["version"] != "reasonscript-input/1.0" {
        return Err(error("unsupported input ABI version"));
    }
    let entries = abi["entries"]
        .as_object()
        .ok_or_else(|| error("invalid entry layouts"))?;
    let matches: Vec<_> = entries
        .keys()
        .filter(|id| {
            id.as_str() == entry
                || id.strip_prefix("fn.") == Some(entry)
                || id.rsplit("::").next() == Some(entry)
        })
        .collect();
    if matches.len() != 1 {
        return Err(error(
            "entry must identify exactly one public typed function",
        ));
    }
    let id = matches[0];
    let params = entries[id]["parameters"]
        .as_object()
        .ok_or_else(|| error("invalid parameter layout"))?;
    let values = input
        .as_object()
        .ok_or_else(|| error("inputs must be a named JSON object"))?;
    if params.len() != values.len() || params.keys().any(|name| !values.contains_key(name)) {
        return Err(error("missing or unexpected input arguments"));
    }
    if let Some(max_bytes) = limits.max_bytes {
        serde_json::to_writer(ByteBudget(max_bytes), input)
            .map_err(|_| error("input byte budget exceeded"))?;
    }
    let mut admission = limits.max_elements;
    for (name, ty) in params {
        admit(&values[name], ty, &abi["structs"], 0, &mut admission)?;
    }
    let mut budget = limits.max_elements;
    let mut result = HashMap::new();
    for (name, ty) in params {
        result.insert(
            name.clone(),
            decode(&values[name], ty, &abi["structs"], 0, &mut budget)?,
        );
    }
    Ok((id.clone(), result))
}

fn decode(
    value: &Json,
    ty: &Json,
    structs: &Json,
    depth: usize,
    budget: &mut usize,
) -> Result<Value, RuntimeError> {
    if depth > 64 || *budget == 0 {
        return Err(error("input nesting or element budget exceeded"));
    }
    *budget -= 1;
    match ty.as_str() {
        Some("Int") => {
            return value
                .as_i64()
                .map(Value::Int)
                .ok_or_else(|| error("expected signed 64-bit Int"))
        }
        Some("Float") => {
            return value
                .as_f64()
                .filter(|n| n.is_finite())
                .map(Value::Float)
                .ok_or_else(|| error("expected finite Float"))
        }
        Some("String") => {
            return value
                .as_str()
                .map(|s| Value::String(Rc::from(s)))
                .ok_or_else(|| error("expected String"))
        }
        Some("Bool") => {
            return value
                .as_bool()
                .map(Value::Bool)
                .ok_or_else(|| error("expected Bool"))
        }
        Some("Null") if value.is_null() => return Ok(Value::Null),
        _ => {}
    }
    if let Some(element) = ty.get("array") {
        let items = value.as_array().ok_or_else(|| error("expected Array"))?;
        if items.len() > *budget {
            return Err(error("input element budget exceeded"));
        }
        let items = items
            .iter()
            .map(|v| decode(v, element, structs, depth + 1, budget))
            .collect::<Result<Vec<_>, _>>()?;
        return Ok(Value::Array(Rc::new(RefCell::new(items))));
    }
    if let Some(types) = ty.get("tuple").and_then(Json::as_array) {
        let items = value
            .as_array()
            .filter(|v| v.len() == types.len())
            .ok_or_else(|| error("tuple length mismatch"))?;
        let items = items
            .iter()
            .zip(types)
            .map(|(v, t)| decode(v, t, structs, depth + 1, budget))
            .collect::<Result<Vec<_>, _>>()?;
        return Ok(Value::Array(Rc::new(RefCell::new(items))));
    }
    if let Some(inner) = ty.get("optional") {
        return if value.is_null() {
            Ok(Value::Optional(None))
        } else {
            Ok(Value::Optional(Some(Box::new(decode(
                value,
                inner,
                structs,
                depth + 1,
                budget,
            )?))))
        };
    }
    if let Some(name) = ty.get("struct").and_then(Json::as_str) {
        let spec = structs
            .get(name)
            .ok_or_else(|| error("unknown struct input layout"))?;
        let fields = spec["fields"]
            .as_object()
            .ok_or_else(|| error("invalid struct layout"))?;
        let object = value
            .as_object()
            .ok_or_else(|| error("expected Struct object"))?;
        if object.len() != fields.len() || fields.keys().any(|k| !object.contains_key(k)) {
            return Err(error(format!("missing or unexpected fields for {name}")));
        }
        let fields = fields
            .iter()
            .map(|(k, t)| {
                Ok((
                    k.clone(),
                    decode(&object[k], t, structs, depth + 1, budget)?,
                ))
            })
            .collect::<Result<HashMap<_, _>, RuntimeError>>()?;
        return Ok(Value::Struct(Rc::new(StructValue {
            type_name: spec["type_name"]
                .as_str()
                .ok_or_else(|| error("invalid struct type name"))?
                .into(),
            fields: RefCell::new(fields),
        })));
    }
    Err(error("unsupported input type"))
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn program(ty: Json) -> Program {
        serde_json::from_value(json!({
            "schema":"reason-computation-ir/0.2", "functions":[], "calculations":[],
            "input_abi":{"version":"reasonscript-input/1.0",
                "entries":{"fn.Test::Identity":{"parameters":{"value":ty}}},"structs":{}}
        }))
        .unwrap()
    }

    #[test]
    fn legacy_default_boundary_is_unchanged() {
        let p = program(json!({"array":"Int"}));
        assert!(arguments(&p, "Identity", &json!({"value":vec![1;99_999]})).is_ok());
        let input = json!({"value":vec![1;100_000]});
        assert_eq!(
            arguments(&p, "Identity", &input).unwrap_err().code,
            "RTH-INPUT-001"
        );
        assert!(arguments_with_limits(
            &p,
            "Identity",
            &input,
            InputLimits {
                max_elements: 100_001,
                max_bytes: Some(1_000_000)
            }
        )
        .is_ok());
    }

    #[test]
    fn nested_records_cannot_allocate_past_the_budget() {
        let mut p = program(json!({"array":{"struct":"Row"}}));
        p.input_abi.as_mut().unwrap()["structs"] =
            json!({"Row":{"type_name":"Row","fields":{"a":"Int","b":"Int"}}});
        let input = json!({"value":[{"a":1,"b":2},{"a":3,"b":4}]});
        assert!(arguments_with_limits(
            &p,
            "Identity",
            &input,
            InputLimits {
                max_elements: 7,
                max_bytes: None
            }
        )
        .is_ok());
        assert!(arguments_with_limits(
            &p,
            "Identity",
            &input,
            InputLimits {
                max_elements: 6,
                max_bytes: None
            }
        )
        .is_err());
    }

    #[test]
    fn optional_layout_nodes_keep_their_existing_charge() {
        let p = program(json!({"optional":"Int"}));
        assert!(arguments_with_limits(
            &p,
            "Identity",
            &json!({"value":null}),
            InputLimits {
                max_elements: 1,
                max_bytes: None
            }
        )
        .is_ok());
        assert!(arguments_with_limits(
            &p,
            "Identity",
            &json!({"value":1}),
            InputLimits {
                max_elements: 1,
                max_bytes: None
            }
        )
        .is_err());
        assert!(arguments_with_limits(
            &p,
            "Identity",
            &json!({"value":1}),
            InputLimits {
                max_elements: 2,
                max_bytes: None
            }
        )
        .is_ok());
    }

    #[test]
    fn utf8_byte_boundary_is_exact_and_optional() {
        let p = program(json!("String"));
        let input = json!({"value":"界\n\""});
        let n = serde_json::to_vec(&input).unwrap().len();
        assert!(arguments_with_limits(
            &p,
            "Identity",
            &input,
            InputLimits {
                max_elements: 1,
                max_bytes: Some(n)
            }
        )
        .is_ok());
        assert!(arguments_with_limits(
            &p,
            "Identity",
            &input,
            InputLimits {
                max_elements: 1,
                max_bytes: Some(n - 1)
            }
        )
        .is_err());
        assert!(arguments(&p, "Identity", &json!({"value":"x".repeat(1_100_000)})).is_ok());
    }

    #[test]
    fn higher_limits_do_not_relax_types_shapes_or_depth() {
        let limits = InputLimits {
            max_elements: MAX_INPUT_ELEMENTS,
            max_bytes: Some(MAX_INPUT_BYTES),
        };
        let p = program(json!({"array":"Int"}));
        for input in [
            json!({"value":[true]}),
            json!({"value":[1.5]}),
            json!({"value":[],"extra":0}),
        ] {
            assert!(arguments_with_limits(&p, "Identity", &input, limits).is_err());
        }
        let mut ty = json!("Int");
        let mut value = json!(1);
        for _ in 0..65 {
            ty = json!({"array":ty});
            value = json!([value]);
        }
        assert!(
            arguments_with_limits(&program(ty), "Identity", &json!({"value":value}), limits)
                .is_err()
        );
    }

    #[test]
    fn invalid_configuration_is_bounded() {
        let p = program(json!("Int"));
        let v = json!({"value":1});
        for limits in [
            InputLimits {
                max_elements: 0,
                max_bytes: None,
            },
            InputLimits {
                max_elements: MAX_INPUT_ELEMENTS + 1,
                max_bytes: None,
            },
            InputLimits {
                max_elements: 1,
                max_bytes: Some(0),
            },
            InputLimits {
                max_elements: 1,
                max_bytes: Some(MAX_INPUT_BYTES + 1),
            },
        ] {
            assert!(arguments_with_limits(&p, "Identity", &v, limits).is_err());
        }
    }
}
