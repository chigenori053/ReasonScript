//! Runtime `Value` for the Phase 3 Tensor-less VM.
//!
//! This is a reduced form of the plan's target `Value` enum (section 8):
//! no `Tensor`, `Function`, or `OptimizerState` variants yet, since
//! Phase 3 is explicitly the Tensor-less skeleton. `Array` and `Struct`
//! use `Rc<RefCell<..>>` rather than being stored by value, because
//! ReasonScript arrays and structs have reference/aliasing semantics on
//! the Python side (`values[0] = 99` mutates every binding that aliases
//! the same array) -- storing them by value in Rust would silently
//! diverge from that the first time a program aliased a mutable
//! collection.

use std::cell::RefCell;
use std::collections::HashMap;
use std::fmt;
use std::rc::Rc;

#[derive(Clone, Debug)]
pub enum Value {
    Null,
    Bool(bool),
    Int(i64),
    Float(f64),
    String(Rc<str>),
    Array(Rc<RefCell<Vec<Value>>>),
    Struct(Rc<StructValue>),
}

#[derive(Debug)]
pub struct StructValue {
    pub type_name: String,
    pub fields: RefCell<HashMap<String, Value>>,
}

impl Value {
    /// Recursively clones `Array`/`Struct` contents into fresh, unshared
    /// containers -- matching Python's `copy.deepcopy`, used for the item
    /// argument of `array.append` on the Python side so appending a
    /// mutable value doesn't leave the new array aliasing the original
    /// binding's contents.
    pub fn deep_clone(&self) -> Value {
        match self {
            Value::Array(items) => Value::Array(Rc::new(RefCell::new(
                items.borrow().iter().map(Value::deep_clone).collect(),
            ))),
            Value::Struct(value) => Value::Struct(Rc::new(StructValue {
                type_name: value.type_name.clone(),
                fields: RefCell::new(
                    value
                        .fields
                        .borrow()
                        .iter()
                        .map(|(name, field_value)| (name.clone(), field_value.deep_clone()))
                        .collect(),
                ),
            })),
            other => other.clone(),
        }
    }

    pub fn type_name(&self) -> &'static str {
        match self {
            Value::Null => "Null",
            Value::Bool(_) => "Bool",
            Value::Int(_) => "Int",
            Value::Float(_) => "Float",
            Value::String(_) => "String",
            Value::Array(_) => "Array",
            Value::Struct(_) => "Struct",
        }
    }
}

impl PartialEq for Value {
    fn eq(&self, other: &Self) -> bool {
        match (self, other) {
            (Value::Null, Value::Null) => true,
            (Value::Bool(a), Value::Bool(b)) => a == b,
            (Value::Int(a), Value::Int(b)) => a == b,
            (Value::Float(a), Value::Float(b)) => a == b,
            (Value::String(a), Value::String(b)) => a == b,
            (Value::Array(a), Value::Array(b)) => *a.borrow() == *b.borrow(),
            (Value::Struct(a), Value::Struct(b)) => {
                a.type_name == b.type_name && *a.fields.borrow() == *b.fields.borrow()
            }
            _ => false,
        }
    }
}

impl PartialEq for StructValue {
    fn eq(&self, other: &Self) -> bool {
        self.type_name == other.type_name && *self.fields.borrow() == *other.fields.borrow()
    }
}

impl fmt::Display for Value {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Value::Null => write!(f, "null"),
            Value::Bool(value) => write!(f, "{value}"),
            Value::Int(value) => write!(f, "{value}"),
            Value::Float(value) => write!(f, "{value}"),
            Value::String(value) => write!(f, "{value}"),
            Value::Array(_) => write!(f, "<array>"),
            Value::Struct(value) => write!(f, "<struct {}>", value.type_name),
        }
    }
}

/// Serializes a `Value` the same way the Python IR interpreter's result
/// would round-trip through JSON (`IntegratedComputationResult.to_dict`),
/// so the differential harness can compare Rust and Python output
/// byte-for-byte after JSON decoding on the Python side.
pub fn to_json(value: &Value) -> serde_json::Value {
    match value {
        Value::Null => serde_json::Value::Null,
        Value::Bool(value) => serde_json::Value::Bool(*value),
        Value::Int(value) => serde_json::Value::from(*value),
        Value::Float(value) => serde_json::json!(value),
        Value::String(value) => serde_json::Value::String(value.to_string()),
        Value::Array(items) => {
            serde_json::Value::Array(items.borrow().iter().map(to_json).collect())
        }
        Value::Struct(value) => {
            let mut map = serde_json::Map::new();
            map.insert(
                "type_name".to_string(),
                serde_json::Value::String(value.type_name.clone()),
            );
            let mut fields = serde_json::Map::new();
            for (name, field_value) in value.fields.borrow().iter() {
                fields.insert(name.clone(), to_json(field_value));
            }
            map.insert("fields".to_string(), serde_json::Value::Object(fields));
            serde_json::Value::Object(map)
        }
    }
}
