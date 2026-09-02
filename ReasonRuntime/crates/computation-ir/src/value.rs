//! Runtime `Value`.
//!
//! This is a reduced form of the plan's target `Value` enum (section 8):
//! no `Function`/`OptimizerState` variants yet (those are Phase 5+).
//! `Tensor` holds only a handle id (`tensor_%04d`, matching the Python
//! side's naming) -- the actual `TensorData` lives in the `Vm`'s
//! `TensorStore` (`reasonscript_tensor_core::TensorStore`), not here, so
//! this crate doesn't need a dependency cycle back into `vm.rs` just to
//! define `Value`. `Array` and `Struct` use `Rc<RefCell<..>>` rather than
//! being stored by value, because
//! ReasonScript arrays and structs have reference/aliasing semantics on
//! the Python side (`values[0] = 99` mutates every binding that aliases
//! the same array) -- storing them by value in Rust would silently
//! diverge from that the first time a program aliased a mutable
//! collection.

use std::cell::RefCell;
use std::collections::HashMap;
use std::fmt;
use std::path::PathBuf;
use std::rc::Rc;

use reasonscript_native_reasonunit_runtime::NativeReasonUnitObject;

#[derive(Debug)]
pub struct RuntimeReasonObject {
    pub object: RefCell<NativeReasonUnitObject>,
    pub source_path: PathBuf,
    pub resource_root: PathBuf,
    pub filesystem_write: bool,
}

#[derive(Debug)]
pub struct RuntimeReasonObjectSnapshot {
    pub object: NativeReasonUnitObject,
    pub owner: Rc<RuntimeReasonObject>,
}

#[derive(Debug)]
pub struct RuntimeReasonTransaction {
    pub snapshot: Rc<RuntimeReasonObjectSnapshot>,
    pub operations: Vec<serde_json::Value>,
    pub closed: bool,
}

#[derive(Clone, Debug)]
pub enum Value {
    Null,
    Bool(bool),
    Int(i64),
    Float(f64),
    String(Rc<str>),
    Array(Rc<RefCell<Vec<Value>>>),
    Struct(Rc<StructValue>),
    /// A resolved `EnumName.VariantName` reference (Phase 1 enum
    /// unification). Distinct from `String` so `Color.Red == "Red"` is a
    /// type mismatch (falls to `PartialEq`'s catch-all `_ => false`)
    /// rather than an accidental true.
    Enum {
        enum_name: Rc<str>,
        variant_name: Rc<str>,
    },
    /// `some(x)` / `none` (Phase 1 optional unification). Deliberately not
    /// the same value as `Value::Null`: a `none` is a tagged "absent"
    /// Optional, so `none == null` is false and a match arm for one can't
    /// accidentally catch the other.
    Optional(Option<Box<Value>>),
    Tensor(Rc<str>),
    ReasonObject(Rc<RuntimeReasonObject>),
    ReasonObjectSnapshot(Rc<RuntimeReasonObjectSnapshot>),
    ReasonTransaction(Rc<RefCell<RuntimeReasonTransaction>>),
    Json(Rc<serde_json::Value>),
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
            Value::Json(value) => Value::Json(Rc::new((**value).clone())),
            Value::Optional(inner) => {
                Value::Optional(inner.as_deref().map(|value| Box::new(value.deep_clone())))
            }
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
            Value::Enum { .. } => "Enum",
            Value::Optional(_) => "Optional",
            Value::Tensor(_) => "Tensor",
            Value::ReasonObject(_) => "ReasonObject",
            Value::ReasonObjectSnapshot(_) => "ReasonObjectSnapshot",
            Value::ReasonTransaction(_) => "ReasonTransaction",
            Value::Json(_) => "ReasonValue",
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
            (
                Value::Enum {
                    enum_name: a_enum,
                    variant_name: a_variant,
                },
                Value::Enum {
                    enum_name: b_enum,
                    variant_name: b_variant,
                },
            ) => a_enum == b_enum && a_variant == b_variant,
            (Value::Optional(a), Value::Optional(b)) => a == b,
            (Value::Tensor(a), Value::Tensor(b)) => a == b,
            (Value::ReasonObject(a), Value::ReasonObject(b)) => {
                let a = a.object.borrow();
                let b = b.object.borrow();
                a.object_id == b.object_id && a.revision_id == b.revision_id
            }
            (Value::ReasonObjectSnapshot(a), Value::ReasonObjectSnapshot(b)) => {
                a.object.object_id == b.object.object_id
                    && a.object.revision_id == b.object.revision_id
            }
            (Value::ReasonTransaction(a), Value::ReasonTransaction(b)) => Rc::ptr_eq(a, b),
            (Value::Json(a), Value::Json(b)) => a == b,
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
            Value::Enum {
                enum_name,
                variant_name,
            } => write!(f, "{enum_name}.{variant_name}"),
            Value::Optional(Some(inner)) => write!(f, "Some({inner})"),
            Value::Optional(None) => write!(f, "None"),
            Value::Tensor(id) => write!(f, "<tensor {id}>"),
            Value::ReasonObject(value) => write!(
                f,
                "<reason_object {}>",
                value.object.borrow().object_id.as_str()
            ),
            Value::ReasonObjectSnapshot(value) => {
                write!(
                    f,
                    "<reason_object_snapshot {}>",
                    value.object.object_id.as_str()
                )
            }
            Value::ReasonTransaction(_) => write!(f, "<reason_transaction>"),
            Value::Json(_) => write!(f, "<reason_value>"),
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
        Value::Enum {
            enum_name,
            variant_name,
        } => serde_json::json!({
            "enum_name": enum_name.to_string(),
            "variant_name": variant_name.to_string(),
        }),
        Value::Optional(Some(inner)) => serde_json::json!({
            "optional": "some",
            "value": to_json(inner),
        }),
        Value::Optional(None) => serde_json::json!({ "optional": "none" }),
        Value::Tensor(id) => {
            // A raw Tensor handle has no plain-JSON representation (it's
            // only meaningful against this run's TensorStore); tests that
            // care about a Tensor's contents route it through
            // `tensor.to_array`/`tensor.scalar` first, matching the same
            // scope limit already documented for the Python differential
            // harness (comparing handles across two separate runtimes
            // isn't meaningful).
            serde_json::json!({ "tensor_id": id.to_string() })
        }
        Value::ReasonObject(value) => serde_json::json!({
            "object_id": value.object.borrow().object_id.as_str(),
            "revision_id": value.object.borrow().revision_id.as_str(),
            "status": "loaded",
        }),
        Value::ReasonObjectSnapshot(value) => serde_json::json!({
            "object_id": value.object.object_id.as_str(),
            "revision_id": value.object.revision_id.as_str(),
            "status": "snapshot",
        }),
        Value::ReasonTransaction(value) => {
            let transaction = value.borrow();
            serde_json::json!({
                "object_id": transaction.snapshot.object.object_id.as_str(),
                "source_revision": transaction.snapshot.object.revision_id.as_str(),
                "operation_count": transaction.operations.len(),
                "status": if transaction.closed { "closed" } else { "open" },
            })
        }
        Value::Json(value) => (**value).clone(),
    }
}

pub fn from_json(value: serde_json::Value) -> Value {
    match value {
        serde_json::Value::Null => Value::Null,
        serde_json::Value::Bool(value) => Value::Bool(value),
        serde_json::Value::Number(value) => value
            .as_i64()
            .map(Value::Int)
            .or_else(|| value.as_f64().map(Value::Float))
            .unwrap_or(Value::Null),
        serde_json::Value::String(value) => Value::String(Rc::from(value)),
        serde_json::Value::Array(values) => Value::Array(Rc::new(RefCell::new(
            values.into_iter().map(from_json).collect(),
        ))),
        value @ serde_json::Value::Object(_) => Value::Json(Rc::new(value)),
    }
}
