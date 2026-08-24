//! Dispatches `optimizer.*` IR calls: SGD, Momentum, and Adam/AdamW.
//!
//! Mirrors `frontend/tensor/optimizers.py` (see that module's docstring
//! for the API-shape rationale: every function returns a single Tensor,
//! never a struct, because the language's static type checker cannot
//! resolve field access on a synthetic struct type). Each step is
//! composed from the same broadcast-elementwise primitive
//! (`reasonscript_tensor_core::ops::broadcast_binary`) that
//! `tensor_dispatch::binary` uses, but -- unlike `tensor_dispatch` --
//! results are stored *without* autograd taping: an optimizer step's
//! output is a fresh, untracked Tensor (like `tensor.detach`), never
//! part of the differentiable graph, matching the Python side exactly
//! (`TensorRuntime.sgd`/`.momentum`/`.adam`/`.adamw` call `self.add`/
//! `self.subtract`/... directly rather than through `self.call(...)`,
//! so they never reach `_record_autograd` either).

use std::cell::RefCell;

use reasonscript_tensor_core::{ops, Dtype, TensorData, TensorStore};

use crate::tensor_dispatch::{arg, as_f64, core_err, fetch, operand_id, store_insert};
use crate::value::Value;
use crate::vm::RuntimeError;

type VResult = Result<Value, RuntimeError>;

/// Every internal helper below indexes `args` positionally (directly, or
/// through `fetch_operand`/`required_scalar`/`required_step`, or -- for
/// `momentum`/`adam`/`adamw` -- by cloning specific positions into a
/// reconstructed slice for a shared sub-computation). None of that
/// indexing is bounds-checked on its own, so this upfront count check
/// (mirroring Python's `TensorRuntime._OPTIMIZER_ARGUMENT_COUNTS`) is
/// load-bearing: without it, a short `arguments` list -- unreachable
/// from real `.rsn` source (`frontend/tensor/optimizers.py` enforces
/// the exact count before lowering) but reachable from hand-built IR,
/// e.g. in a test -- would panic on a slice index out of range instead
/// of returning a normal `OPT-002` error.
const ARGUMENT_COUNTS: &[(&str, usize)] = &[
    ("sgd", 3),
    ("momentum_velocity", 3),
    ("momentum", 5),
    ("adam_moment1", 3),
    ("adam_moment2", 3),
    ("adam", 9),
    ("adamw", 10),
];

pub fn call(function_id: &str, args: Vec<Value>, store: &RefCell<TensorStore>) -> VResult {
    let name = function_id.strip_prefix("optimizer.").unwrap_or(function_id);
    let Some(&(_, expected)) = ARGUMENT_COUNTS.iter().find(|(candidate, _)| *candidate == name) else {
        return Err(RuntimeError::new(
            "OPT-001",
            format!("unknown Optimizer function: {function_id}"),
        ));
    };
    if args.len() != expected {
        return Err(RuntimeError::new(
            "OPT-002",
            format!("Optimizer function argument count mismatch: {function_id} expects {expected}"),
        ));
    }
    match name {
        "sgd" => sgd(args, store),
        "momentum_velocity" => momentum_velocity(args, store),
        "momentum" => momentum(args, store),
        "adam_moment1" => adam_moment1(args, store),
        "adam_moment2" => adam_moment2(args, store),
        "adam" => adam(args, store),
        "adamw" => adamw(args, store),
        _ => unreachable!("name was already matched against ARGUMENT_COUNTS above"),
    }
}

fn scalar(value: f64) -> TensorData {
    TensorData {
        shape: Vec::new(),
        dtype: Dtype::F64,
        data: vec![value],
    }
}

fn elementwise(
    left: &TensorData,
    right: &TensorData,
    op: impl Fn(f64, f64) -> f64,
) -> Result<TensorData, RuntimeError> {
    let (shape, dtype, data) = ops::broadcast_binary(left, right, op, None).map_err(core_err)?;
    Ok(TensorData { shape, dtype, data })
}

fn fetch_operand(args: &[Value], index: usize, store: &RefCell<TensorStore>) -> Result<TensorData, RuntimeError> {
    let id = operand_id(args, index, store)?;
    fetch(store, &id)
}

fn required_scalar(args: &[Value], index: usize) -> Result<f64, RuntimeError> {
    let value = arg(args, index)
        .ok_or_else(|| RuntimeError::new("OPT-002", "missing Optimizer scalar argument"))?;
    as_f64(value)
}

fn required_step(args: &[Value], index: usize) -> Result<i64, RuntimeError> {
    match arg(args, index) {
        Some(Value::Int(value)) if *value >= 1 => Ok(*value),
        Some(_) => Err(RuntimeError::new(
            "OPT-005",
            "Optimizer step count must be a positive Int",
        )),
        None => Err(RuntimeError::new("OPT-002", "missing Optimizer step argument")),
    }
}

fn sub(a: &TensorData, b: &TensorData) -> Result<TensorData, RuntimeError> {
    elementwise(a, b, |x, y| x - y)
}

fn mul(a: &TensorData, b: &TensorData) -> Result<TensorData, RuntimeError> {
    elementwise(a, b, |x, y| x * y)
}

fn add(a: &TensorData, b: &TensorData) -> Result<TensorData, RuntimeError> {
    elementwise(a, b, |x, y| x + y)
}

fn div(a: &TensorData, b: &TensorData) -> Result<TensorData, RuntimeError> {
    elementwise(a, b, |x, y| x / y)
}

fn sqrt(a: &TensorData) -> TensorData {
    TensorData {
        shape: a.shape.clone(),
        dtype: a.dtype,
        data: a.data.iter().map(|value| value.sqrt()).collect(),
    }
}

// param, grad, lr
fn sgd(args: Vec<Value>, store: &RefCell<TensorStore>) -> VResult {
    let param = fetch_operand(&args, 0, store)?;
    let grad = fetch_operand(&args, 1, store)?;
    let lr = required_scalar(&args, 2)?;
    let result = sub(&param, &mul(&grad, &scalar(lr))?)?;
    store_insert(store, result.shape, result.dtype, result.data)
}

// grad, velocity, momentum
fn momentum_velocity(args: Vec<Value>, store: &RefCell<TensorStore>) -> VResult {
    let result = momentum_velocity_data(&args, store)?;
    store_insert(store, result.shape, result.dtype, result.data)
}

fn momentum_velocity_data(
    args: &[Value],
    store: &RefCell<TensorStore>,
) -> Result<TensorData, RuntimeError> {
    let grad = fetch_operand(args, 0, store)?;
    let velocity = fetch_operand(args, 1, store)?;
    let momentum = required_scalar(args, 2)?;
    add(&mul(&scalar(momentum), &velocity)?, &grad)
}

// param, grad, velocity, lr, momentum
fn momentum(args: Vec<Value>, store: &RefCell<TensorStore>) -> VResult {
    let param = fetch_operand(&args, 0, store)?;
    let velocity_args = [args[1].clone(), args[2].clone(), args[4].clone()];
    let new_velocity = momentum_velocity_data(&velocity_args, store)?;
    let lr = required_scalar(&args, 3)?;
    let result = sub(&param, &mul(&scalar(lr), &new_velocity)?)?;
    store_insert(store, result.shape, result.dtype, result.data)
}

// grad, m, beta1
fn adam_moment1(args: Vec<Value>, store: &RefCell<TensorStore>) -> VResult {
    let result = adam_moment1_data(&args, store)?;
    store_insert(store, result.shape, result.dtype, result.data)
}

fn adam_moment1_data(args: &[Value], store: &RefCell<TensorStore>) -> Result<TensorData, RuntimeError> {
    let grad = fetch_operand(args, 0, store)?;
    let m = fetch_operand(args, 1, store)?;
    let beta1 = required_scalar(args, 2)?;
    add(&mul(&scalar(beta1), &m)?, &mul(&scalar(1.0 - beta1), &grad)?)
}

// grad, v, beta2
fn adam_moment2(args: Vec<Value>, store: &RefCell<TensorStore>) -> VResult {
    let result = adam_moment2_data(&args, store)?;
    store_insert(store, result.shape, result.dtype, result.data)
}

fn adam_moment2_data(args: &[Value], store: &RefCell<TensorStore>) -> Result<TensorData, RuntimeError> {
    let grad = fetch_operand(args, 0, store)?;
    let v = fetch_operand(args, 1, store)?;
    let beta2 = required_scalar(args, 2)?;
    let grad_sq = mul(&grad, &grad)?;
    add(&mul(&scalar(beta2), &v)?, &mul(&scalar(1.0 - beta2), &grad_sq)?)
}

/// Returns `(update, scaled_update)` where `update = m_hat / (sqrt(v_hat) + eps)`
/// and `scaled_update = lr * update` -- shared by `adam` and `adamw`.
fn adam_update(
    args: &[Value],
    store: &RefCell<TensorStore>,
) -> Result<(TensorData, TensorData), RuntimeError> {
    let step = required_step(args, 4)?;
    let lr = required_scalar(args, 5)?;
    let beta1 = required_scalar(args, 6)?;
    let beta2 = required_scalar(args, 7)?;
    let eps = required_scalar(args, 8)?;

    let moment1_args = [args[1].clone(), args[2].clone(), args[6].clone()];
    let moment2_args = [args[1].clone(), args[3].clone(), args[7].clone()];
    let new_m = adam_moment1_data(&moment1_args, store)?;
    let new_v = adam_moment2_data(&moment2_args, store)?;

    let bias_correction1 = 1.0 - beta1.powf(step as f64);
    let bias_correction2 = 1.0 - beta2.powf(step as f64);
    let m_hat = div(&new_m, &scalar(bias_correction1))?;
    let v_hat = div(&new_v, &scalar(bias_correction2))?;
    let update = div(&m_hat, &add(&sqrt(&v_hat), &scalar(eps))?)?;
    let scaled = mul(&scalar(lr), &update)?;
    Ok((update, scaled))
}

// param, grad, m, v, step, lr, beta1, beta2, eps
fn adam(args: Vec<Value>, store: &RefCell<TensorStore>) -> VResult {
    let param = fetch_operand(&args, 0, store)?;
    let (_update, scaled) = adam_update(&args, store)?;
    let result = sub(&param, &scaled)?;
    store_insert(store, result.shape, result.dtype, result.data)
}

// param, grad, m, v, step, lr, beta1, beta2, eps, weight_decay
fn adamw(args: Vec<Value>, store: &RefCell<TensorStore>) -> VResult {
    let param = fetch_operand(&args, 0, store)?;
    let (_update, scaled) = adam_update(&args, store)?;
    let lr = required_scalar(&args, 5)?;
    let weight_decay = required_scalar(&args, 9)?;
    let decay = mul(&scalar(lr), &mul(&scalar(weight_decay), &param)?)?;
    let result = sub(&sub(&param, &scaled)?, &decay)?;
    store_insert(store, result.shape, result.dtype, result.data)
}
