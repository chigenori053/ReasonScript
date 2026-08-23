//! Reverse-mode autograd tape and VJPs, matching
//! `frontend/tensor/runtime.py`'s `_GradNode` / `_record_autograd` /
//! `TensorRuntime.grad` / `TensorRuntime._vjp` for the forward ops this
//! crate implements (see `ops.rs` / `AGENTS.md` for the exact list).
//!
//! VJPs are NOT implemented here for ops this crate doesn't have forward
//! support for (`concat`/`stack`/`slice`/`narrow`/`softmax`/`linear`/
//! `conv2d`/`max_pool2d`/`avg_pool2d`) -- consistent with Phase 4's own
//! scope boundary, not a new gap.

use std::collections::{HashMap, HashSet};

use crate::error::{Result, TensorCoreError};
use crate::shape::{all_coords, broadcast_flat_index, coords, flat_index, normalize_axis, product};
use crate::store::{TensorData, TensorStore};

/// One recorded forward operation, enough information to compute its
/// VJP without re-deriving axis/keep_dims/etc. from a generic argument
/// list (unlike Python, which replays `node.arguments`/`node.attributes`
/// generically -- explicit variants are clearer in Rust and just as
/// faithful, since each maps 1:1 to one of `_vjp`'s `name in {...}`
/// branches).
#[derive(Clone, Debug)]
pub enum GradOp {
    Broadcast2 {
        name: String,
        left: String,
        right: String,
    },
    Unary1 {
        name: String,
        input: String,
    },
    ShapePassthrough {
        input: String,
    },
    Transpose {
        input: String,
        axis_a: usize,
        axis_b: usize,
    },
    Reduce {
        name: String,
        input: String,
        axes: Vec<usize>,
        keep_dims: bool,
    },
    MinMax {
        name: String,
        input: String,
        axes: Vec<usize>,
        keep_dims: bool,
    },
    MatMul {
        left: String,
        right: String,
    },
    Dot {
        left: String,
        right: String,
    },
    Norm {
        input: String,
        order: i64,
    },
}

impl GradOp {
    fn input_ids(&self) -> Vec<&str> {
        match self {
            GradOp::Broadcast2 { left, right, .. } => vec![left.as_str(), right.as_str()],
            GradOp::Unary1 { input, .. } => vec![input.as_str()],
            GradOp::ShapePassthrough { input } => vec![input.as_str()],
            GradOp::Transpose { input, .. } => vec![input.as_str()],
            GradOp::Reduce { input, .. } => vec![input.as_str()],
            GradOp::MinMax { input, .. } => vec![input.as_str()],
            GradOp::MatMul { left, right } => vec![left.as_str(), right.as_str()],
            GradOp::Dot { left, right } => vec![left.as_str(), right.as_str()],
            GradOp::Norm { input, .. } => vec![input.as_str()],
        }
    }
}

#[derive(Default)]
pub struct Autograd {
    pub requires_grad: HashSet<String>,
    nodes: Vec<(String, GradOp)>,
}

impl Autograd {
    /// Mirrors `_record_autograd`: only tapes the op (and marks its
    /// output grad-tracked) if at least one input already is.
    pub fn record(&mut self, output_id: &str, op: GradOp) {
        let tracked = op
            .input_ids()
            .iter()
            .any(|id| self.requires_grad.contains(*id));
        if !tracked {
            return;
        }
        self.requires_grad.insert(output_id.to_string());
        self.nodes.push((output_id.to_string(), op));
    }

    pub fn mark_parameter(&mut self, tensor_id: &str) {
        self.requires_grad.insert(tensor_id.to_string());
    }

    pub fn is_tracked(&self, tensor_id: &str) -> bool {
        self.requires_grad.contains(tensor_id)
    }

    /// Mirrors `TensorRuntime.grad`: walks the tape in reverse from
    /// `loss_id`, accumulating gradients, and returns the accumulated
    /// (or zero, if unreached) gradient data for each requested
    /// parameter, in the same order as `parameter_ids`.
    pub fn grad(
        &self,
        store: &TensorStore,
        loss_id: &str,
        parameter_ids: &[&str],
    ) -> Result<Vec<(Vec<usize>, crate::dtype::Dtype, Vec<f64>)>> {
        let loss = store.get(loss_id)?;
        if loss.data.len() != 1 {
            return Err(TensorCoreError::new(
                "AD-001",
                "tensor.grad requires a scalar floating loss",
            ));
        }
        for parameter_id in parameter_ids {
            if !self.requires_grad.contains(*parameter_id) {
                return Err(TensorCoreError::new(
                    "AD-003",
                    "gradient target is not a parameter",
                ));
            }
        }
        let mut gradients: HashMap<String, Vec<f64>> = HashMap::new();
        gradients.insert(loss_id.to_string(), vec![1.0]);
        for (output_id, op) in self.nodes.iter().rev() {
            let upstream = match gradients.get(output_id) {
                Some(value) => value.clone(),
                None => continue,
            };
            for (reference, contribution) in vjp(op, &upstream, store)? {
                gradients
                    .entry(reference)
                    .and_modify(|existing| {
                        for (slot, value) in existing.iter_mut().zip(contribution.iter()) {
                            *slot += value;
                        }
                    })
                    .or_insert(contribution);
            }
        }
        let mut results = Vec::with_capacity(parameter_ids.len());
        for parameter_id in parameter_ids {
            let tensor = store.get(parameter_id)?;
            let values = gradients
                .get(*parameter_id)
                .cloned()
                .unwrap_or_else(|| vec![0.0; tensor.data.len()]);
            results.push((tensor.shape.clone(), tensor.dtype, values));
        }
        Ok(results)
    }
}

fn vjp(op: &GradOp, upstream: &[f64], store: &TensorStore) -> Result<Vec<(String, Vec<f64>)>> {
    match op {
        GradOp::Broadcast2 { name, left, right } => {
            broadcast2_vjp(name, left, right, upstream, store)
        }
        GradOp::Unary1 { name, input } => unary1_vjp(name, input, upstream, store),
        GradOp::ShapePassthrough { input } => {
            let source = store.get(input)?;
            Ok(vec![(
                input.clone(),
                upstream[..source.data.len()].to_vec(),
            )])
        }
        GradOp::Transpose {
            input,
            axis_a,
            axis_b,
        } => transpose_vjp(input, *axis_a, *axis_b, upstream, store),
        GradOp::Reduce {
            name,
            input,
            axes,
            keep_dims,
        } => reduce_vjp(name, input, axes, *keep_dims, upstream, store),
        GradOp::MinMax {
            name,
            input,
            axes,
            keep_dims,
        } => minmax_vjp(name, input, axes, *keep_dims, upstream, store),
        GradOp::MatMul { left, right } => matmul_vjp(left, right, upstream, store),
        GradOp::Dot { left, right } => dot_vjp(left, right, upstream, store),
        GradOp::Norm { input, order } => norm_vjp(input, *order, upstream, store),
    }
}

fn broadcast2_vjp(
    name: &str,
    left_id: &str,
    right_id: &str,
    upstream: &[f64],
    store: &TensorStore,
) -> Result<Vec<(String, Vec<f64>)>> {
    let left = store.get(left_id)?;
    let right = store.get(right_id)?;
    let output_shape = crate::shape::broadcast_shape(&left.shape, &right.shape)?;
    let mut left_grad = vec![0.0; left.data.len()];
    let mut right_grad = vec![0.0; right.data.len()];
    for out_coords in all_coords(&output_shape) {
        let flat = flat_index(&out_coords, &output_shape);
        let grad_value = upstream[flat];
        let left_index = broadcast_flat_index(&out_coords, &left.shape);
        let right_index = broadcast_flat_index(&out_coords, &right.shape);
        let x = left.data[left_index];
        let y = right.data[right_index];
        let (dx, dy) = match name {
            "add" => (grad_value, grad_value),
            "subtract" => (grad_value, -grad_value),
            "multiply" => (grad_value * y, grad_value * x),
            "divide" => (grad_value / y, -grad_value * x / (y * y)),
            "power" => (
                grad_value * y * x.powf(y - 1.0),
                if x > 0.0 {
                    grad_value * x.powf(y) * x.ln()
                } else {
                    0.0
                },
            ),
            "maximum" => (
                if x >= y { grad_value } else { 0.0 },
                if y > x { grad_value } else { 0.0 },
            ),
            "minimum" => (
                if x <= y { grad_value } else { 0.0 },
                if y < x { grad_value } else { 0.0 },
            ),
            other => {
                return Err(TensorCoreError::new(
                    "AD-004",
                    format!("no VJP for broadcast op: {other}"),
                ))
            }
        };
        left_grad[left_index] += dx;
        right_grad[right_index] += dy;
    }
    Ok(vec![
        (left_id.to_string(), left_grad),
        (right_id.to_string(), right_grad),
    ])
}

fn unary1_vjp(
    name: &str,
    input_id: &str,
    upstream: &[f64],
    store: &TensorStore,
) -> Result<Vec<(String, Vec<f64>)>> {
    let source = store.get(input_id)?;
    let mut values = Vec::with_capacity(source.data.len());
    for (&item, &grad_value) in source.data.iter().zip(upstream.iter()) {
        let derivative = match name {
            "negate" => -1.0,
            "abs" => {
                if item > 0.0 {
                    1.0
                } else if item < 0.0 {
                    -1.0
                } else {
                    0.0
                }
            }
            "exp" => item.exp(),
            "log" => 1.0 / item,
            "sqrt" => 0.5 / item.sqrt(),
            other => {
                return Err(TensorCoreError::new(
                    "AD-004",
                    format!("no VJP for unary op: {other}"),
                ))
            }
        };
        values.push(grad_value * derivative);
    }
    Ok(vec![(input_id.to_string(), values)])
}

fn transpose_vjp(
    input_id: &str,
    axis_a: usize,
    axis_b: usize,
    upstream: &[f64],
    store: &TensorStore,
) -> Result<Vec<(String, Vec<f64>)>> {
    let source = store.get(input_id)?;
    let mut output_shape = source.shape.clone();
    output_shape.swap(axis_a, axis_b);
    let mut values = vec![0.0; source.data.len()];
    for (index, &grad_value) in upstream.iter().enumerate() {
        let mut coordinate = coords(index, &output_shape);
        coordinate.swap(axis_a, axis_b);
        values[flat_index(&coordinate, &source.shape)] += grad_value;
    }
    Ok(vec![(input_id.to_string(), values)])
}

fn reduce_vjp(
    name: &str,
    input_id: &str,
    axes: &[usize],
    keep_dims: bool,
    upstream: &[f64],
    store: &TensorStore,
) -> Result<Vec<(String, Vec<f64>)>> {
    let source = store.get(input_id)?;
    let out_shape = reduced_shape(&source.shape, axes, keep_dims);
    let divisor = if name == "mean" {
        axes.iter()
            .map(|&axis| source.shape[axis] as f64)
            .product::<f64>()
    } else {
        1.0
    };
    let mut values = Vec::with_capacity(source.data.len());
    for coordinate in all_coords(&source.shape) {
        let out_coordinate = collapse_coordinate(&coordinate, axes, keep_dims);
        let flat = flat_index(&out_coordinate, &out_shape);
        values.push(upstream[flat] / divisor);
    }
    Ok(vec![(input_id.to_string(), values)])
}

fn minmax_vjp(
    name: &str,
    input_id: &str,
    axes: &[usize],
    keep_dims: bool,
    upstream: &[f64],
    store: &TensorStore,
) -> Result<Vec<(String, Vec<f64>)>> {
    let source = store.get(input_id)?;
    let out_shape = reduced_shape(&source.shape, axes, keep_dims);
    let mut values = vec![0.0; source.data.len()];
    let mut selected: HashMap<Vec<usize>, usize> = HashMap::new();
    for (index, coordinate) in all_coords(&source.shape).into_iter().enumerate() {
        let key = collapse_coordinate(&coordinate, axes, keep_dims);
        let candidate = source.data[index];
        selected
            .entry(key)
            .and_modify(|current| {
                let current_value = source.data[*current];
                let better = if name == "min" {
                    candidate < current_value
                } else {
                    candidate > current_value
                };
                if better {
                    *current = index;
                }
            })
            .or_insert(index);
    }
    for (key, index) in selected {
        let flat = flat_index(&key, &out_shape);
        values[index] += upstream[flat];
    }
    Ok(vec![(input_id.to_string(), values)])
}

fn matmul_vjp(
    left_id: &str,
    right_id: &str,
    upstream: &[f64],
    store: &TensorStore,
) -> Result<Vec<(String, Vec<f64>)>> {
    let left = store.get(left_id)?;
    let right = store.get(right_id)?;
    let (m, k) = (left.shape[0], left.shape[1]);
    let n = right.shape[1];
    let mut left_grad = vec![0.0; left.data.len()];
    let mut right_grad = vec![0.0; right.data.len()];
    for row in 0..m {
        for col in 0..n {
            let grad_value = upstream[row * n + col];
            for inner in 0..k {
                left_grad[row * k + inner] += grad_value * right.data[inner * n + col];
                right_grad[inner * n + col] += grad_value * left.data[row * k + inner];
            }
        }
    }
    Ok(vec![
        (left_id.to_string(), left_grad),
        (right_id.to_string(), right_grad),
    ])
}

fn dot_vjp(
    left_id: &str,
    right_id: &str,
    upstream: &[f64],
    store: &TensorStore,
) -> Result<Vec<(String, Vec<f64>)>> {
    let left = store.get(left_id)?;
    let right = store.get(right_id)?;
    let grad_value = upstream[0];
    let left_grad: Vec<f64> = right.data.iter().map(|&item| grad_value * item).collect();
    let right_grad: Vec<f64> = left.data.iter().map(|&item| grad_value * item).collect();
    Ok(vec![
        (left_id.to_string(), left_grad),
        (right_id.to_string(), right_grad),
    ])
}

fn norm_vjp(
    input_id: &str,
    order: i64,
    upstream: &[f64],
    store: &TensorStore,
) -> Result<Vec<(String, Vec<f64>)>> {
    let source = store.get(input_id)?;
    let grad_value = upstream[0];
    let values: Vec<f64> = if order == 1 {
        source
            .data
            .iter()
            .map(|&item| {
                grad_value
                    * if item > 0.0 {
                        1.0
                    } else if item < 0.0 {
                        -1.0
                    } else {
                        0.0
                    }
            })
            .collect()
    } else {
        let denominator = source
            .data
            .iter()
            .map(|value| value * value)
            .sum::<f64>()
            .sqrt();
        source
            .data
            .iter()
            .map(|&item| {
                if denominator != 0.0 {
                    grad_value * item / denominator
                } else {
                    0.0
                }
            })
            .collect()
    };
    Ok(vec![(input_id.to_string(), values)])
}

fn reduced_shape(shape: &[usize], axes: &[usize], keep_dims: bool) -> Vec<usize> {
    if keep_dims {
        shape
            .iter()
            .enumerate()
            .map(|(i, &size)| if axes.contains(&i) { 1 } else { size })
            .collect()
    } else {
        shape
            .iter()
            .enumerate()
            .filter(|(i, _)| !axes.contains(i))
            .map(|(_, &size)| size)
            .collect()
    }
}

fn collapse_coordinate(coordinate: &[usize], axes: &[usize], keep_dims: bool) -> Vec<usize> {
    if keep_dims {
        coordinate
            .iter()
            .enumerate()
            .map(|(i, &c)| if axes.contains(&i) { 0 } else { c })
            .collect()
    } else {
        coordinate
            .iter()
            .enumerate()
            .filter(|(i, _)| !axes.contains(i))
            .map(|(_, &c)| c)
            .collect()
    }
}

pub fn resolve_axes(axis: Option<&[i64]>, rank: usize) -> Result<Vec<usize>> {
    match axis {
        None => Ok((0..rank).collect()),
        Some(list) => list
            .iter()
            .map(|&value| normalize_axis(value, rank, false))
            .collect(),
    }
}

pub fn count(shape: &[usize]) -> usize {
    product(shape)
}

pub fn require_f32_or_f64(tensor: &TensorData) -> Result<()> {
    match tensor.dtype {
        crate::dtype::Dtype::F32 | crate::dtype::Dtype::F64 => Ok(()),
        _ => Err(TensorCoreError::new(
            "AD-002",
            "parameters must use f32 or f64",
        )),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::dtype::Dtype;
    use crate::ops;

    /// `loss = sum(a + a*b)`. Analytically d(loss)/d(a_i) = 1 + b_i and
    /// d(loss)/d(b_i) = a_i. Builds the same tape `tensor_dispatch.rs`
    /// would (multiply, then add, then sum, each taped via
    /// `insert_with_grad`), and checks the VJP-derived gradient against
    /// straight finite differences on the untraced forward computation
    /// -- the Phase 5 gate's "finite difference" check, exercised here
    /// without needing a Python process at all.
    fn forward_loss(a: &[f64], b: &[f64]) -> f64 {
        let a_tensor = TensorData {
            shape: vec![3],
            dtype: Dtype::F64,
            data: a.to_vec(),
        };
        let b_tensor = TensorData {
            shape: vec![3],
            dtype: Dtype::F64,
            data: b.to_vec(),
        };
        let (_, _, c) = ops::broadcast_binary(&a_tensor, &b_tensor, |x, y| x * y, None).unwrap();
        let c_tensor = TensorData {
            shape: vec![3],
            dtype: Dtype::F64,
            data: c,
        };
        let (_, _, d) = ops::broadcast_binary(&a_tensor, &c_tensor, |x, y| x + y, None).unwrap();
        d.iter().sum()
    }

    #[test]
    fn multiply_add_sum_gradient_matches_finite_differences() {
        let mut store = TensorStore::new();
        let a_id = store
            .insert(vec![3], Dtype::F64, vec![2.0, -3.0, 1.5])
            .unwrap();
        let b_id = store
            .insert(vec![3], Dtype::F64, vec![1.0, 2.0, 0.5])
            .unwrap();
        store.autograd.mark_parameter(&a_id);
        store.autograd.mark_parameter(&b_id);

        let a = store.get(&a_id).unwrap().clone();
        let b = store.get(&b_id).unwrap().clone();
        let (c_shape, c_dtype, c_data) = ops::broadcast_binary(&a, &b, |x, y| x * y, None).unwrap();
        let c_id = store
            .insert_with_grad(
                c_shape,
                c_dtype,
                c_data,
                GradOp::Broadcast2 {
                    name: "multiply".into(),
                    left: a_id.clone(),
                    right: b_id.clone(),
                },
            )
            .unwrap();

        let a = store.get(&a_id).unwrap().clone();
        let c = store.get(&c_id).unwrap().clone();
        let (d_shape, d_dtype, d_data) = ops::broadcast_binary(&a, &c, |x, y| x + y, None).unwrap();
        let d_id = store
            .insert_with_grad(
                d_shape,
                d_dtype,
                d_data,
                GradOp::Broadcast2 {
                    name: "add".into(),
                    left: a_id.clone(),
                    right: c_id.clone(),
                },
            )
            .unwrap();

        let d = store.get(&d_id).unwrap().clone();
        let (loss_shape, loss_dtype, loss_data) =
            ops::reduce(&d, None, false, ops::ReduceOp::Sum).unwrap();
        let loss_id = store
            .insert_with_grad(
                loss_shape,
                loss_dtype,
                loss_data,
                GradOp::Reduce {
                    name: "sum".into(),
                    input: d_id.clone(),
                    axes: vec![0],
                    keep_dims: false,
                },
            )
            .unwrap();

        let grads = store
            .autograd
            .grad(&store, &loss_id, &[a_id.as_str(), b_id.as_str()])
            .unwrap();
        let (_, _, a_grad) = &grads[0];
        let (_, _, b_grad) = &grads[1];

        let a0 = vec![2.0, -3.0, 1.5];
        let b0 = vec![1.0, 2.0, 0.5];
        let epsilon = 1e-6;
        for i in 0..3 {
            let mut a_plus = a0.clone();
            a_plus[i] += epsilon;
            let mut a_minus = a0.clone();
            a_minus[i] -= epsilon;
            let numeric =
                (forward_loss(&a_plus, &b0) - forward_loss(&a_minus, &b0)) / (2.0 * epsilon);
            assert!(
                (numeric - a_grad[i]).abs() < 1e-4,
                "d(loss)/d(a[{i}]): analytic={} numeric={numeric}",
                a_grad[i]
            );

            let mut b_plus = b0.clone();
            b_plus[i] += epsilon;
            let mut b_minus = b0.clone();
            b_minus[i] -= epsilon;
            let numeric =
                (forward_loss(&a0, &b_plus) - forward_loss(&a0, &b_minus)) / (2.0 * epsilon);
            assert!(
                (numeric - b_grad[i]).abs() < 1e-4,
                "d(loss)/d(b[{i}]): analytic={} numeric={numeric}",
                b_grad[i]
            );
        }

        // Cross-check against the closed form directly too.
        for i in 0..3 {
            assert!((a_grad[i] - (1.0 + b0[i])).abs() < 1e-9);
            assert!((b_grad[i] - a0[i]).abs() < 1e-9);
        }
    }

    #[test]
    fn grad_of_non_parameter_is_rejected() {
        let mut store = TensorStore::new();
        let a_id = store.insert(vec![1], Dtype::F64, vec![1.0]).unwrap();
        let loss_id = store.insert(vec![1], Dtype::F64, vec![1.0]).unwrap();
        let error = store
            .autograd
            .grad(&store, &loss_id, &[a_id.as_str()])
            .unwrap_err();
        assert_eq!(error.code, "AD-003");
    }
}
