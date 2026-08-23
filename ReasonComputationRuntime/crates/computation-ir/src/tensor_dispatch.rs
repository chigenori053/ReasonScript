//! Dispatches `tensor.*` IR calls to `reasonscript_tensor_core`.
//!
//! Implements the Phase 4 "Rust Tensor forward" subset: creation,
//! inspection, shape ops (reshape/flatten/transpose/squeeze/unsqueeze),
//! broadcast binary ops, comparisons, elementwise unary ops, reductions,
//! dot/matmul/norm, cast, to_array/scalar, the four `random_*` RNG
//! functions, and `.rstensor` load/save -- ~50 of the 65 Tensor Standard
//! Functions. Deliberately NOT implemented here (return
//! `RT-UNSUPPORTED-001`, not a wrong answer or a panic): `slice`,
//! `narrow`, `gather`, `concat`, `stack` (indexing-heavy shape ops),
//! `relu`/`softmax`/`linear`/`conv2d`/`max_pool2d`/`avg_pool2d`
//! (neural-net inference ops), and `parameter`/`detach`/`requires_grad`/
//! `grad` (autograd, Phase 5 scope).
//!
//! Argument handling: ReasonScript Tensor calls are always positional in
//! `.rsn` source (no keyword-argument syntax), so this mirrors each
//! Python method's positional parameter order and default values
//! exactly.

use std::cell::RefCell;
use std::rc::Rc;

use reasonscript_tensor_core::{ops, rng, Dtype, TensorData, TensorStore};

use crate::value::Value;
use crate::vm::RuntimeError;

type VResult = Result<Value, RuntimeError>;

pub fn call(function_id: &str, args: Vec<Value>, store: &RefCell<TensorStore>) -> VResult {
    let name = function_id.strip_prefix("tensor.").unwrap_or(function_id);
    match name {
        "create" => create(args, store),
        "zeros" => fill(args, store, 0.0),
        "ones" => fill(args, store, 1.0),
        "full" => full(args, store),
        "shape" => shape(args, store),
        "rank" => rank(args, store),
        "size" => size(args, store),
        "dtype" => dtype(args, store),
        "dimension" => dimension(args, store),
        "reshape" => reshape(args, store),
        "flatten" => flatten(args, store),
        "transpose" => transpose(args, store),
        "squeeze" => squeeze(args, store),
        "unsqueeze" => unsqueeze(args, store),
        "add" => binary(args, store, |a, b| a + b, None),
        "subtract" => binary(args, store, |a, b| a - b, None),
        "multiply" => binary(args, store, |a, b| a * b, None),
        "divide" => divide(args, store),
        "power" => binary(args, store, |a, b| a.powf(b), None),
        "maximum" => binary(args, store, f64::max, None),
        "minimum" => binary(args, store, f64::min, None),
        "equal" => compare(args, store, |a, b| a == b),
        "not_equal" => compare(args, store, |a, b| a != b),
        "greater" => compare(args, store, |a, b| a > b),
        "greater_equal" => compare(args, store, |a, b| a >= b),
        "less" => compare(args, store, |a, b| a < b),
        "less_equal" => compare(args, store, |a, b| a <= b),
        "negate" => unary(args, store, |v| -v, None),
        "abs" => unary(args, store, f64::abs, None),
        "exp" => unary(args, store, f64::exp, None),
        "log" => unary(args, store, f64::ln, None),
        "sqrt" => unary(args, store, f64::sqrt, None),
        "sum" => reduce(args, store, ops::ReduceOp::Sum),
        "mean" => reduce(args, store, ops::ReduceOp::Mean),
        "min" => reduce(args, store, ops::ReduceOp::Min),
        "max" => reduce(args, store, ops::ReduceOp::Max),
        "argmax" => arg_reduce(args, store, ops::ArgOp::Max),
        "argmin" => arg_reduce(args, store, ops::ArgOp::Min),
        "dot" => binary_linalg(args, store, ops::dot),
        "matmul" => binary_linalg(args, store, ops::matmul),
        "norm" => norm(args, store),
        "cast" => cast(args, store),
        "to_array" => to_array(args, store),
        "scalar" => scalar(args, store),
        "random_uniform" => random_uniform(args, store),
        "random_normal" => random_normal(args, store),
        "random_bernoulli" => random_bernoulli(args, store),
        "random_permutation" => random_permutation(args, store),
        "load" => load(args, store),
        "save" => save(args, store),
        _ => Err(RuntimeError::new(
            "RT-UNSUPPORTED-001",
            format!("{function_id}: not implemented in the Rust Tensor VM (Phase 4 scope)"),
        )),
    }
}

// ---- argument extraction -------------------------------------------------

fn arg(args: &[Value], index: usize) -> Option<&Value> {
    args.get(index)
}

fn tensor_id(args: &[Value], index: usize) -> Result<Rc<str>, RuntimeError> {
    match arg(args, index) {
        Some(Value::Tensor(id)) => Ok(id.clone()),
        Some(other) => Err(RuntimeError::new(
            "RT-CALL-005",
            format!("expected a Tensor argument, got {}", other.type_name()),
        )),
        None => Err(RuntimeError::new("RT-CALL-002", "missing Tensor argument")),
    }
}

fn as_f64(value: &Value) -> Result<f64, RuntimeError> {
    match value {
        Value::Int(v) => Ok(*v as f64),
        Value::Float(v) => Ok(*v),
        other => Err(RuntimeError::new(
            "RT-CALL-005",
            format!("expected a number, got {}", other.type_name()),
        )),
    }
}

fn as_i64(value: &Value) -> Result<i64, RuntimeError> {
    match value {
        Value::Int(v) => Ok(*v),
        other => Err(RuntimeError::new(
            "RT-CALL-005",
            format!("expected an Int, got {}", other.type_name()),
        )),
    }
}

fn as_str(value: &Value) -> Result<String, RuntimeError> {
    match value {
        Value::String(v) => Ok(v.to_string()),
        other => Err(RuntimeError::new(
            "RT-CALL-005",
            format!("expected a String, got {}", other.type_name()),
        )),
    }
}

fn required_f64(args: &[Value], index: usize, default: Option<f64>) -> Result<f64, RuntimeError> {
    match arg(args, index) {
        Some(value) => as_f64(value),
        None => default.ok_or_else(|| RuntimeError::new("RT-CALL-002", "missing argument")),
    }
}

fn required_i64(args: &[Value], index: usize, default: Option<i64>) -> Result<i64, RuntimeError> {
    match arg(args, index) {
        Some(value) => as_i64(value),
        None => default.ok_or_else(|| RuntimeError::new("RT-CALL-002", "missing argument")),
    }
}

fn required_dtype(
    args: &[Value],
    index: usize,
    default: Option<&str>,
) -> Result<Dtype, RuntimeError> {
    let name = match arg(args, index) {
        Some(value) => as_str(value)?,
        None => default
            .ok_or_else(|| RuntimeError::new("RT-CALL-002", "missing dtype argument"))?
            .to_string(),
    };
    Dtype::parse(&name).map_err(core_err)
}

fn as_shape(value: &Value) -> Result<Vec<usize>, RuntimeError> {
    match value {
        Value::Array(items) => items
            .borrow()
            .iter()
            .map(|item| Ok(as_i64(item)?.max(0) as usize))
            .collect(),
        other => Err(RuntimeError::new(
            "RT-CALL-005",
            format!("expected a shape array, got {}", other.type_name()),
        )),
    }
}

fn as_i64_list(value: &Value) -> Result<Vec<i64>, RuntimeError> {
    match value {
        Value::Array(items) => items.borrow().iter().map(as_i64).collect(),
        other => Err(RuntimeError::new(
            "RT-CALL-005",
            format!("expected an Int array, got {}", other.type_name()),
        )),
    }
}

fn optional_axis(args: &[Value], index: usize) -> Result<Option<i64>, RuntimeError> {
    match arg(args, index) {
        None | Some(Value::Null) => Ok(None),
        Some(value) => Ok(Some(as_i64(value)?)),
    }
}

fn optional_axis_list(args: &[Value], index: usize) -> Result<Option<Vec<i64>>, RuntimeError> {
    match arg(args, index) {
        None | Some(Value::Null) => Ok(None),
        Some(Value::Array(_)) => Ok(Some(as_i64_list(arg(args, index).unwrap())?)),
        Some(value) => Ok(Some(vec![as_i64(value)?])),
    }
}

fn optional_bool(args: &[Value], index: usize, default: bool) -> Result<bool, RuntimeError> {
    match arg(args, index) {
        None => Ok(default),
        Some(Value::Bool(value)) => Ok(*value),
        Some(other) => Err(RuntimeError::new(
            "RT-CALL-005",
            format!("expected a Bool, got {}", other.type_name()),
        )),
    }
}

fn core_err(error: reasonscript_tensor_core::TensorCoreError) -> RuntimeError {
    RuntimeError::new(&error.code, error.message)
}

fn json_to_value(json: serde_json::Value) -> Value {
    match json {
        serde_json::Value::Null => Value::Null,
        serde_json::Value::Bool(v) => Value::Bool(v),
        serde_json::Value::Number(v) => {
            if let Some(i) = v.as_i64() {
                Value::Int(i)
            } else {
                Value::Float(v.as_f64().unwrap_or(0.0))
            }
        }
        serde_json::Value::String(v) => Value::String(Rc::from(v.as_str())),
        serde_json::Value::Array(items) => Value::Array(Rc::new(RefCell::new(
            items.into_iter().map(json_to_value).collect(),
        ))),
        serde_json::Value::Object(_) => Value::Null, // not used for Tensor results
    }
}

fn store_insert(
    store: &RefCell<TensorStore>,
    shape: Vec<usize>,
    dtype: Dtype,
    data: Vec<f64>,
) -> VResult {
    let id = store
        .borrow_mut()
        .insert(shape, dtype, data)
        .map_err(core_err)?;
    Ok(Value::Tensor(Rc::from(id.as_str())))
}

fn fetch(store: &RefCell<TensorStore>, id: &str) -> Result<TensorData, RuntimeError> {
    store
        .borrow()
        .get(id)
        .map(|tensor| tensor.clone())
        .map_err(core_err)
}

// ---- creation --------------------------------------------------------

fn create(args: Vec<Value>, store: &RefCell<TensorStore>) -> VResult {
    let data_value = arg(&args, 0)
        .ok_or_else(|| RuntimeError::new("RT-CALL-002", "tensor.create requires data"))?;
    let json = crate::value::to_json(data_value);
    let (shape, flat, inferred_dtype) =
        reasonscript_tensor_core::json::shape_and_flat(&json).map_err(core_err)?;
    let dtype = match arg(&args, 1) {
        Some(Value::Null) | None => inferred_dtype,
        Some(value) => Dtype::parse(&as_str(value)?).map_err(core_err)?,
    };
    store_insert(store, shape, dtype, flat)
}

fn fill(args: Vec<Value>, store: &RefCell<TensorStore>, value: f64) -> VResult {
    let shape_value =
        arg(&args, 0).ok_or_else(|| RuntimeError::new("RT-CALL-002", "missing shape"))?;
    let shape = as_shape(shape_value)?;
    let dtype = required_dtype(&args, 1, Some("f32"))?;
    let count = shape.iter().product();
    store_insert(store, shape, dtype, vec![value; count])
}

fn full(args: Vec<Value>, store: &RefCell<TensorStore>) -> VResult {
    let shape_value =
        arg(&args, 0).ok_or_else(|| RuntimeError::new("RT-CALL-002", "missing shape"))?;
    let shape = as_shape(shape_value)?;
    let value = required_f64(&args, 1, None)?;
    let dtype = required_dtype(&args, 2, Some("f32"))?;
    let count = shape.iter().product();
    store_insert(store, shape, dtype, vec![value; count])
}

// ---- inspection --------------------------------------------------------

fn shape(args: Vec<Value>, store: &RefCell<TensorStore>) -> VResult {
    let tensor = fetch(store, &tensor_id(&args, 0)?)?;
    Ok(Value::Array(Rc::new(RefCell::new(
        tensor
            .shape
            .iter()
            .map(|&size| Value::Int(size as i64))
            .collect(),
    ))))
}

fn rank(args: Vec<Value>, store: &RefCell<TensorStore>) -> VResult {
    let tensor = fetch(store, &tensor_id(&args, 0)?)?;
    Ok(Value::Int(tensor.shape.len() as i64))
}

fn size(args: Vec<Value>, store: &RefCell<TensorStore>) -> VResult {
    let tensor = fetch(store, &tensor_id(&args, 0)?)?;
    Ok(Value::Int(tensor.data.len() as i64))
}

fn dtype(args: Vec<Value>, store: &RefCell<TensorStore>) -> VResult {
    let tensor = fetch(store, &tensor_id(&args, 0)?)?;
    Ok(Value::String(Rc::from(tensor.dtype.name())))
}

fn dimension(args: Vec<Value>, store: &RefCell<TensorStore>) -> VResult {
    let tensor = fetch(store, &tensor_id(&args, 0)?)?;
    let axis = required_i64(&args, 1, None)?;
    let normalized =
        reasonscript_tensor_core::shape::normalize_axis(axis, tensor.shape.len(), false)
            .map_err(core_err)?;
    Ok(Value::Int(tensor.shape[normalized] as i64))
}

// ---- shape ops --------------------------------------------------------

fn reshape(args: Vec<Value>, store: &RefCell<TensorStore>) -> VResult {
    let tensor = fetch(store, &tensor_id(&args, 0)?)?;
    let target = as_i64_list(
        arg(&args, 1).ok_or_else(|| RuntimeError::new("RT-CALL-002", "missing shape"))?,
    )?;
    let (shape, dtype, data) = ops::reshape(&tensor, &target).map_err(core_err)?;
    store_insert(store, shape, dtype, data)
}

fn flatten(args: Vec<Value>, store: &RefCell<TensorStore>) -> VResult {
    let tensor = fetch(store, &tensor_id(&args, 0)?)?;
    let count = tensor.data.len() as i64;
    let (shape, dtype, data) = ops::reshape(&tensor, &[count]).map_err(core_err)?;
    store_insert(store, shape, dtype, data)
}

fn transpose(args: Vec<Value>, store: &RefCell<TensorStore>) -> VResult {
    let tensor = fetch(store, &tensor_id(&args, 0)?)?;
    let axis_a = required_i64(&args, 1, Some(0))?;
    let axis_b = required_i64(&args, 2, Some(1))?;
    let (shape, dtype, data) = ops::transpose(&tensor, axis_a, axis_b).map_err(core_err)?;
    store_insert(store, shape, dtype, data)
}

fn squeeze(args: Vec<Value>, store: &RefCell<TensorStore>) -> VResult {
    let tensor = fetch(store, &tensor_id(&args, 0)?)?;
    let axis = optional_axis(&args, 1)?;
    let (shape, dtype, data) = ops::squeeze(&tensor, axis).map_err(core_err)?;
    store_insert(store, shape, dtype, data)
}

fn unsqueeze(args: Vec<Value>, store: &RefCell<TensorStore>) -> VResult {
    let tensor = fetch(store, &tensor_id(&args, 0)?)?;
    let axis = required_i64(&args, 1, None)?;
    let (shape, dtype, data) = ops::unsqueeze(&tensor, axis).map_err(core_err)?;
    store_insert(store, shape, dtype, data)
}

// ---- broadcast / elementwise --------------------------------------------

fn binary(
    args: Vec<Value>,
    store: &RefCell<TensorStore>,
    op: impl Fn(f64, f64) -> f64,
    result_dtype: Option<Dtype>,
) -> VResult {
    let left = fetch(store, &tensor_id(&args, 0)?)?;
    let right = fetch(store, &tensor_id(&args, 1)?)?;
    let (shape, dtype, data) =
        ops::broadcast_binary(&left, &right, op, result_dtype).map_err(core_err)?;
    store_insert(store, shape, dtype, data)
}

/// Python's `float / 0.0` raises `ZeroDivisionError` at the moment of
/// computation (unlike IEEE-754 `f64` division, which silently produces
/// `inf`/`NaN`); `TensorRuntime.call()` catches that generically and
/// re-raises it as `TensorError("TSF-012", ...)`. Pre-checking for a
/// zero divisor and reporting the same TSF-012 reproduces that exactly,
/// rather than letting Rust silently compute `inf` and have the
/// finite-value check reject it as a different code (TSF-010).
fn divide(args: Vec<Value>, store: &RefCell<TensorStore>) -> VResult {
    let left = fetch(store, &tensor_id(&args, 0)?)?;
    let right = fetch(store, &tensor_id(&args, 1)?)?;
    if right.data.iter().any(|&value| value == 0.0) {
        return Err(RuntimeError::new(
            "TSF-012",
            "Tensor backend execution failed",
        ));
    }
    let (shape, dtype, data) =
        ops::broadcast_binary(&left, &right, |a, b| a / b, None).map_err(core_err)?;
    store_insert(store, shape, dtype, data)
}

fn compare(
    args: Vec<Value>,
    store: &RefCell<TensorStore>,
    op: impl Fn(f64, f64) -> bool,
) -> VResult {
    let left = fetch(store, &tensor_id(&args, 0)?)?;
    let right = fetch(store, &tensor_id(&args, 1)?)?;
    let (shape, dtype, data) = ops::comparison(&left, &right, op).map_err(core_err)?;
    store_insert(store, shape, dtype, data)
}

fn unary(
    args: Vec<Value>,
    store: &RefCell<TensorStore>,
    op: impl Fn(f64) -> f64,
    result_dtype: Option<Dtype>,
) -> VResult {
    let tensor = fetch(store, &tensor_id(&args, 0)?)?;
    let (shape, dtype, data) = ops::unary(&tensor, op, result_dtype);
    store_insert(store, shape, dtype, data)
}

// ---- reduction --------------------------------------------------------

fn reduce(args: Vec<Value>, store: &RefCell<TensorStore>, op: ops::ReduceOp) -> VResult {
    let tensor = fetch(store, &tensor_id(&args, 0)?)?;
    let axis = optional_axis_list(&args, 1)?;
    let keep_dims = optional_bool(&args, 2, false)?;
    let (shape, dtype, data) =
        ops::reduce(&tensor, axis.as_deref(), keep_dims, op).map_err(core_err)?;
    store_insert(store, shape, dtype, data)
}

fn arg_reduce(args: Vec<Value>, store: &RefCell<TensorStore>, op: ops::ArgOp) -> VResult {
    let tensor = fetch(store, &tensor_id(&args, 0)?)?;
    let axis = optional_axis(&args, 1)?;
    let keep_dims = optional_bool(&args, 2, false)?;
    let (shape, dtype, data) = ops::arg_reduce(&tensor, axis, keep_dims, op).map_err(core_err)?;
    store_insert(store, shape, dtype, data)
}

// ---- linear algebra --------------------------------------------------------

fn binary_linalg(
    args: Vec<Value>,
    store: &RefCell<TensorStore>,
    op: impl Fn(
        &TensorData,
        &TensorData,
    ) -> reasonscript_tensor_core::Result<(Vec<usize>, Dtype, Vec<f64>)>,
) -> VResult {
    let left = fetch(store, &tensor_id(&args, 0)?)?;
    let right = fetch(store, &tensor_id(&args, 1)?)?;
    let (shape, dtype, data) = op(&left, &right).map_err(core_err)?;
    store_insert(store, shape, dtype, data)
}

fn norm(args: Vec<Value>, store: &RefCell<TensorStore>) -> VResult {
    let tensor = fetch(store, &tensor_id(&args, 0)?)?;
    let order = required_i64(&args, 1, Some(2))?;
    let (shape, dtype, data) = ops::norm(&tensor, order).map_err(core_err)?;
    store_insert(store, shape, dtype, data)
}

// ---- conversion --------------------------------------------------------

fn cast(args: Vec<Value>, store: &RefCell<TensorStore>) -> VResult {
    let tensor = fetch(store, &tensor_id(&args, 0)?)?;
    let dtype = required_dtype(&args, 1, None)?;
    store_insert(store, tensor.shape.clone(), dtype, tensor.data.clone())
}

fn to_array(args: Vec<Value>, store: &RefCell<TensorStore>) -> VResult {
    let tensor = fetch(store, &tensor_id(&args, 0)?)?;
    Ok(json_to_value(reasonscript_tensor_core::json::nested_json(
        &tensor,
    )))
}

fn scalar(args: Vec<Value>, store: &RefCell<TensorStore>) -> VResult {
    let tensor = fetch(store, &tensor_id(&args, 0)?)?;
    let json = reasonscript_tensor_core::json::scalar_json(&tensor).map_err(core_err)?;
    Ok(json_to_value(json))
}

// ---- RNG --------------------------------------------------------

fn random_uniform(args: Vec<Value>, store: &RefCell<TensorStore>) -> VResult {
    let shape =
        as_shape(arg(&args, 0).ok_or_else(|| RuntimeError::new("RT-CALL-002", "missing shape"))?)?;
    let low = required_f64(&args, 1, Some(0.0))?;
    let high = required_f64(&args, 2, Some(1.0))?;
    let seed = required_i64(&args, 3, Some(0))?;
    let stream = required_i64(&args, 4, Some(0))?;
    let dtype = required_dtype(&args, 5, Some("f32"))?;
    let count = shape.iter().product();
    let data = rng::uniform(low, high, seed, stream, count).map_err(core_err)?;
    store_insert(store, shape, dtype, data)
}

fn random_normal(args: Vec<Value>, store: &RefCell<TensorStore>) -> VResult {
    let shape =
        as_shape(arg(&args, 0).ok_or_else(|| RuntimeError::new("RT-CALL-002", "missing shape"))?)?;
    let mean = required_f64(&args, 1, Some(0.0))?;
    let std = required_f64(&args, 2, Some(1.0))?;
    let seed = required_i64(&args, 3, Some(0))?;
    let stream = required_i64(&args, 4, Some(0))?;
    let dtype = required_dtype(&args, 5, Some("f32"))?;
    let count = shape.iter().product();
    let data = rng::normal(mean, std, seed, stream, count).map_err(core_err)?;
    store_insert(store, shape, dtype, data)
}

fn random_bernoulli(args: Vec<Value>, store: &RefCell<TensorStore>) -> VResult {
    let shape =
        as_shape(arg(&args, 0).ok_or_else(|| RuntimeError::new("RT-CALL-002", "missing shape"))?)?;
    let probability = required_f64(&args, 1, Some(0.5))?;
    let seed = required_i64(&args, 2, Some(0))?;
    let stream = required_i64(&args, 3, Some(0))?;
    let count = shape.iter().product();
    let data = rng::bernoulli(probability, seed, stream, count).map_err(core_err)?;
    store_insert(store, shape, Dtype::Bool, data)
}

fn random_permutation(args: Vec<Value>, store: &RefCell<TensorStore>) -> VResult {
    let size = required_i64(&args, 0, None)?;
    let seed = required_i64(&args, 1, Some(0))?;
    let stream = required_i64(&args, 2, Some(0))?;
    let data = rng::permutation(size, seed, stream).map_err(core_err)?;
    store_insert(store, vec![size.max(0) as usize], Dtype::I64, data)
}

// ---- I/O --------------------------------------------------------

fn load(args: Vec<Value>, store: &RefCell<TensorStore>) -> VResult {
    let path =
        as_str(arg(&args, 0).ok_or_else(|| RuntimeError::new("RT-CALL-002", "missing path"))?)?;
    let bytes = std::fs::read(&path).map_err(|error| {
        RuntimeError::new("TIO-003", format!("Tensor file cannot be read: {error}"))
    })?;
    let tensor = reasonscript_tensor_core::io::decode(&bytes).map_err(core_err)?;
    store_insert(store, tensor.shape, tensor.dtype, tensor.data)
}

fn save(args: Vec<Value>, store: &RefCell<TensorStore>) -> VResult {
    let tensor = fetch(store, &tensor_id(&args, 0)?)?;
    let path =
        as_str(arg(&args, 1).ok_or_else(|| RuntimeError::new("RT-CALL-002", "missing path"))?)?;
    let (payload, checksum) = reasonscript_tensor_core::io::encode(&tensor);
    if let Some(parent) = std::path::Path::new(&path).parent() {
        if !parent.as_os_str().is_empty() {
            std::fs::create_dir_all(parent).map_err(|error| {
                RuntimeError::new("TIO-005", format!("atomic Tensor write failed: {error}"))
            })?;
        }
    }
    std::fs::write(&path, &payload).map_err(|error| {
        RuntimeError::new("TIO-005", format!("atomic Tensor write failed: {error}"))
    })?;
    let mut fields = std::collections::HashMap::new();
    fields.insert(
        "profile".to_string(),
        Value::String(Rc::from(reasonscript_tensor_core::io::PROFILE)),
    );
    fields.insert("path".to_string(), Value::String(Rc::from(path.as_str())));
    fields.insert("byte_size".to_string(), Value::Int(payload.len() as i64));
    fields.insert(
        "checksum".to_string(),
        Value::String(Rc::from(format!("sha256:{checksum}").as_str())),
    );
    Ok(Value::Struct(Rc::new(crate::value::StructValue {
        type_name: "TensorArtifactReceipt".to_string(),
        fields: RefCell::new(fields),
    })))
}
