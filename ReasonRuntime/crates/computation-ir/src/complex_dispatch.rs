//! Bounded complex arithmetic using the core VM's ordinary structs and arrays.
//! No compiler, VM, allocator or application-specific reasoning policy lives here.
use crate::numeric::as_f64;
use crate::value::StructValue;
use crate::{RuntimeError, Value};
use std::{cell::RefCell, collections::HashMap, rc::Rc};
type C = (f64, f64);
type Result<T> = std::result::Result<T, RuntimeError>;
const MAX_VECTOR: usize = 4096;
const MAX_MATRIX: usize = 64;
fn err(code: &str, text: &str) -> RuntimeError {
    RuntimeError::new(code, text)
}
fn finite(z: C) -> Result<C> {
    if z.0.is_finite() && z.1.is_finite() {
        Ok(z)
    } else {
        Err(err("CXR-OVERFLOW", "non-finite complex result"))
    }
}
fn number(v: &Value) -> Result<f64> {
    as_f64(v)
        .filter(|n| n.is_finite())
        .ok_or_else(|| err("CXR-TYPE", "expected finite number"))
}
fn object(name: &str, fields: impl IntoIterator<Item = (String, Value)>) -> Value {
    Value::Struct(Rc::new(StructValue {
        type_name: name.into(),
        fields: RefCell::new(fields.into_iter().collect::<HashMap<_, _>>()),
    }))
}
fn value(z: C) -> Value {
    object(
        "Complex",
        [
            ("re".into(), Value::Float(z.0)),
            ("im".into(), Value::Float(z.1)),
        ],
    )
}
fn scalar(v: &Value) -> Result<C> {
    if let Value::Struct(s) = v {
        if s.type_name == "Complex" {
            let f = s.fields.borrow();
            if f.len() == 2 {
                if let (Some(re), Some(im)) = (f.get("re"), f.get("im")) {
                    return finite((number(re)?, number(im)?));
                }
            }
        }
    }
    Err(err("CXR-TYPE", "expected Complex { re, im }"))
}
fn array(v: &Value, max: usize) -> Result<Vec<Value>> {
    match v {
        Value::Array(a) if a.borrow().len() <= max => Ok(a.borrow().clone()),
        Value::Array(_) => Err(err(
            "CXR-LIMIT",
            "complex collection dimension limit exceeded",
        )),
        _ => Err(err("CXR-TYPE", "expected complex array")),
    }
}
fn vector(v: &Value) -> Result<Vec<C>> {
    array(v, MAX_VECTOR)?.iter().map(scalar).collect()
}
fn vector_value(v: Vec<C>) -> Value {
    Value::Array(Rc::new(RefCell::new(v.into_iter().map(value).collect())))
}
fn matrix(v: &Value) -> Result<Vec<Vec<C>>> {
    let rows: Vec<Vec<C>> = array(v, MAX_MATRIX)?
        .iter()
        .map(|row| array(row, MAX_MATRIX)?.iter().map(scalar).collect())
        .collect::<Result<_>>()?;
    if rows.is_empty() || rows[0].is_empty() || rows.iter().any(|r| r.len() != rows[0].len()) {
        return Err(err("CXR-SHAPE", "matrix must be nonempty and rectangular"));
    }
    Ok(rows)
}
fn mul(a: C, b: C) -> Result<C> {
    finite((a.0 * b.0 - a.1 * b.1, a.0 * b.1 + a.1 * b.0))
}
fn add(a: C, b: C) -> Result<C> {
    finite((a.0 + b.0, a.1 + b.1))
}
fn dot(a: &[C], b: &[C], hermitian: bool) -> Result<C> {
    if a.len() != b.len() {
        return Err(err("CXR-SHAPE", "vector dimensions differ"));
    }
    let mut z = (0.0, 0.0);
    for (&x, &y) in a.iter().zip(b) {
        z = add(z, mul((x.0, if hermitian { -x.1 } else { x.1 }), y)?)?;
    }
    Ok(z)
}
fn state(v: &Value) -> Result<(Vec<C>, i64)> {
    if let Value::Struct(s) = v {
        let f = s.fields.borrow();
        if s.type_name == "ComplexState" && f.len() == 2 {
            if let (Some(a), Some(Value::Int(revision))) = (f.get("amplitudes"), f.get("revision"))
            {
                if *revision >= 0 {
                    let a = vector(a)?;
                    if !a.is_empty() {
                        return Ok((a, *revision));
                    }
                }
            }
        }
    }
    Err(err(
        "CXR-TYPE",
        "expected nonempty ComplexState with nonnegative revision",
    ))
}
fn state_value(a: Vec<C>, revision: i64) -> Value {
    object(
        "ComplexState",
        [
            ("amplitudes".into(), vector_value(a)),
            ("revision".into(), Value::Int(revision)),
        ],
    )
}

pub fn call(id: &str, args: Vec<Value>) -> Result<Value> {
    let arity = match id {
        "complex.conjugate" | "complex.abs" | "complex.phase" | "complex.state" => 1,
        "complex.scalar" | "complex.add" | "complex.sub" | "complex.mul" | "complex.div"
        | "complex.vector_add" | "complex.vector_sub" | "complex.scale" | "complex.inner"
        | "complex.matmul" | "complex.transition" => 2,
        _ => return Err(err("CXR-001", "unknown complex operation")),
    };
    if args.len() != arity {
        return Err(err("CXR-002", "wrong complex argument count"));
    }
    let a = &args[0];
    Ok(match id {
        "complex.scalar" => value((number(a)?, number(&args[1])?)),
        "complex.add" => value(add(scalar(a)?, scalar(&args[1])?)?),
        "complex.sub" => {
            let y = scalar(&args[1])?;
            value(add(scalar(a)?, (-y.0, -y.1))?)
        }
        "complex.mul" => value(mul(scalar(a)?, scalar(&args[1])?)?),
        "complex.div" => {
            let x = scalar(a)?;
            let y = scalar(&args[1])?;
            let scale = y.0.abs().max(y.1.abs());
            if scale == 0.0 {
                return Err(err("CXR-DIVZERO", "complex division by zero"));
            }
            let (r, i) = (y.0 / scale, y.1 / scale);
            let d = r * r + i * i;
            value(finite((
                ((x.0 / scale) * r + (x.1 / scale) * i) / d,
                ((x.1 / scale) * r - (x.0 / scale) * i) / d,
            ))?)
        }
        "complex.conjugate" => {
            let x = scalar(a)?;
            value((x.0, -x.1))
        }
        "complex.abs" => {
            let x = scalar(a)?;
            Value::Float(finite((x.0.hypot(x.1), 0.0))?.0)
        }
        "complex.phase" => {
            let x = scalar(a)?;
            Value::Float(if x.0 == 0.0 && x.1 == 0.0 {
                0.0
            } else {
                x.1.atan2(x.0)
            })
        }
        "complex.vector_add" | "complex.vector_sub" => {
            let x = vector(a)?;
            let y = vector(&args[1])?;
            if x.len() != y.len() {
                return Err(err("CXR-SHAPE", "vector dimensions differ"));
            }
            let sign = if id == "complex.vector_sub" {
                -1.0
            } else {
                1.0
            };
            vector_value(
                x.into_iter()
                    .zip(y)
                    .map(|(x, y)| add(x, (sign * y.0, sign * y.1)))
                    .collect::<Result<_>>()?,
            )
        }
        "complex.scale" => {
            let x = vector(a)?;
            let y = scalar(&args[1])?;
            vector_value(x.into_iter().map(|x| mul(x, y)).collect::<Result<_>>()?)
        }
        "complex.inner" => value(dot(&vector(a)?, &vector(&args[1])?, true)?),
        "complex.matmul" => {
            let x = matrix(a)?;
            let y = matrix(&args[1])?;
            if x[0].len() != y.len() {
                return Err(err("CXR-SHAPE", "matrix dimensions differ"));
            }
            let mut rows = Vec::new();
            for row in x {
                let mut out = Vec::new();
                for j in 0..y[0].len() {
                    out.push(dot(
                        &row,
                        &y.iter().map(|r| r[j]).collect::<Vec<_>>(),
                        false,
                    )?);
                }
                rows.push(vector_value(out));
            }
            Value::Array(Rc::new(RefCell::new(rows)))
        }
        "complex.state" => {
            let x = vector(a)?;
            if x.is_empty() {
                return Err(err("CXR-SHAPE", "empty complex state"));
            }
            state_value(x, 0)
        }
        "complex.transition" => {
            let (x, revision) = state(a)?;
            let m = matrix(&args[1])?;
            if m.len() != x.len() || m[0].len() != x.len() {
                return Err(err(
                    "CXR-SHAPE",
                    "transition matrix must be square and match state",
                ));
            }
            let next = m
                .iter()
                .map(|row| dot(row, &x, false))
                .collect::<Result<_>>()?;
            state_value(
                next,
                revision
                    .checked_add(1)
                    .ok_or_else(|| err("CXR-OVERFLOW", "complex state revision overflow"))?,
            )
        }
        _ => unreachable!(),
    })
}
