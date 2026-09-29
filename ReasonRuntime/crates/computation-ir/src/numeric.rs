//! General-purpose numeric semantics shared by the VM and the foundation
//! namespaces (`math.*`, `sequence.*`, `serialize.*`).
//!
//! Contract (see `docs/language-reference.md`, "Numeric semantics"):
//!
//! - `Int` is a signed 64-bit integer. Integer arithmetic that leaves that
//!   range fails with [`OVERFLOW`] instead of wrapping.
//! - `Float` is an IEEE-754 binary64 value that is always finite. An
//!   operation whose exact result would be `NaN` or `±Infinity` fails with
//!   [`OVERFLOW`] (magnitude too large) or [`NON_FINITE`] instead of
//!   introducing a non-finite value into ordinary computation.
//! - Underflow is defined behavior: a result too small to represent
//!   rounds to a subnormal value or to a signed zero, as IEEE-754 does.
//! - Mixed `Int`/`Float` arithmetic promotes the `Int` operand to `Float`.
//! - Mixed `Int`/`Float` comparison compares exact mathematical values,
//!   so it never depends on the rounding of an `Int` to `Float`.

use std::cmp::Ordering;

use crate::value::Value;
use crate::vm::RuntimeError;

/// A finite operation produced a magnitude outside the representable range.
pub const OVERFLOW: &str = "RT-NUM-OVERFLOW";
/// An operation would have produced `NaN`.
pub const NON_FINITE: &str = "RT-NUM-NONFINITE";
/// A float-to-int conversion received a value outside the Int range.
pub const CONVERSION: &str = "RT-NUM-CONVERSION";

/// Numeric view of an `Int` or `Float` value (`Bool` is not numeric).
pub fn as_f64(value: &Value) -> Option<f64> {
    match value {
        Value::Int(value) => Some(*value as f64),
        Value::Float(value) => Some(*value),
        _ => None,
    }
}

/// Accepts a finite float result, otherwise reports the stable diagnostic.
pub fn finite(operation: &str, value: f64) -> Result<f64, RuntimeError> {
    if value.is_finite() {
        Ok(value)
    } else if value.is_nan() {
        Err(RuntimeError::new(
            NON_FINITE,
            format!("{operation} produced a non-finite (NaN) value"),
        ))
    } else {
        Err(RuntimeError::new(
            OVERFLOW,
            format!("{operation} overflows the finite Float range"),
        ))
    }
}

/// Exact ordering between an `Int` and a finite `Float`.
fn compare_int_float(integer: i64, float: f64) -> Option<Ordering> {
    if float.is_nan() {
        return None;
    }
    // 2^63 is exactly representable; every i64 is below it.
    const TWO_POW_63: f64 = 9_223_372_036_854_775_808.0;
    if float >= TWO_POW_63 {
        return Some(Ordering::Less);
    }
    if float < -TWO_POW_63 {
        return Some(Ordering::Greater);
    }
    let truncated = float.trunc();
    // `truncated` is integral and within [-2^63, 2^63), so the cast is exact.
    let whole = truncated as i64;
    match integer.cmp(&whole) {
        Ordering::Equal => {
            let fraction = float - truncated;
            if fraction > 0.0 {
                Some(Ordering::Less)
            } else if fraction < 0.0 {
                Some(Ordering::Greater)
            } else {
                Some(Ordering::Equal)
            }
        }
        other => Some(other),
    }
}

/// Ordering for a mixed `Int`/`Float` pair; `None` when the pair is not mixed.
pub fn compare_mixed(left: &Value, right: &Value) -> Option<Ordering> {
    match (left, right) {
        (Value::Int(a), Value::Float(b)) => compare_int_float(*a, *b),
        (Value::Float(a), Value::Int(b)) => compare_int_float(*b, *a).map(Ordering::reverse),
        _ => None,
    }
}

/// Converts a finite float to Int, truncating toward zero.
pub fn truncate_to_int(value: f64, operation: &str) -> Result<i64, RuntimeError> {
    const TWO_POW_63: f64 = 9_223_372_036_854_775_808.0;
    let truncated = value.trunc();
    if !(-TWO_POW_63..TWO_POW_63).contains(&truncated) {
        return Err(RuntimeError::new(
            CONVERSION,
            format!("{operation} value is outside the 64-bit Int range"),
        ));
    }
    Ok(truncated as i64)
}

/// Built-in `int(x)` / `float(x)` casts.
///
/// `int(Int)` is the identity, `int(Float)` truncates toward zero and
/// rejects values outside the Int range, and `float(x)` converts to the
/// nearest binary64 value.
pub fn cast(name: &str, value: Value) -> Result<Value, RuntimeError> {
    match (name, value) {
        ("int", Value::Int(value)) => Ok(Value::Int(value)),
        ("int", Value::Float(value)) => truncate_to_int(value, "int()").map(Value::Int),
        ("float", Value::Int(value)) => Ok(Value::Float(value as f64)),
        ("float", Value::Float(value)) => Ok(Value::Float(value)),
        (name, other) => Err(RuntimeError::new(
            "RT-CALL-005",
            format!(
                "{name}() argument must be Int or Float, got {}",
                other.type_name()
            ),
        )),
    }
}

/// Canonical, locale-independent text for a finite float.
///
/// - Zero is `0.0` or `-0.0` (the sign is preserved).
/// - Values with `1e-7 <= |x| < 1e21` use positional notation with the
///   shortest digits that round-trip, and always contain a `.`.
/// - Other values use the shortest round-trip scientific form, e.g.
///   `1e21`, `1.5e-8`, `-2.5e300`.
///
/// Every output is a valid JSON number and parses back to the same value.
pub fn canonical_float(value: f64) -> String {
    if value == 0.0 {
        return if value.is_sign_negative() {
            "-0.0"
        } else {
            "0.0"
        }
        .to_string();
    }
    let magnitude = value.abs();
    if (1e-7..1e21).contains(&magnitude) {
        let text = format!("{value}");
        if text.contains('.') {
            text
        } else {
            format!("{text}.0")
        }
    } else {
        format!("{value:e}")
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn mixed_comparison_is_exact() {
        assert_eq!(compare_int_float(3, 3.0), Some(Ordering::Equal));
        assert_eq!(compare_int_float(1, 1.5), Some(Ordering::Less));
        assert_eq!(compare_int_float(-1, -1.5), Some(Ordering::Greater));
        // 2^53 + 1 is not representable as f64; exact comparison still
        // distinguishes it from 2^53.
        assert_eq!(
            compare_int_float(9_007_199_254_740_993, 9_007_199_254_740_992.0),
            Some(Ordering::Greater)
        );
        assert_eq!(compare_int_float(i64::MAX, 1e19), Some(Ordering::Less));
        assert_eq!(compare_int_float(i64::MIN, -1e19), Some(Ordering::Greater));
    }

    #[test]
    fn canonical_float_forms() {
        assert_eq!(canonical_float(0.0), "0.0");
        assert_eq!(canonical_float(-0.0), "-0.0");
        assert_eq!(canonical_float(1.0), "1.0");
        assert_eq!(canonical_float(0.1 + 0.2), "0.30000000000000004");
        assert_eq!(canonical_float(1e21), "1e21");
        assert_eq!(canonical_float(123456789.0), "123456789.0");
        assert_eq!(canonical_float(1.5e-8), "1.5e-8");
        assert_eq!(canonical_float(-2.5e300), "-2.5e300");
        assert_eq!(canonical_float(5e-324), "5e-324");
        for value in [
            0.1,
            1e-7,
            9.999e20,
            1e21,
            5e-324,
            f64::MAX,
            -f64::MIN_POSITIVE,
        ] {
            assert_eq!(canonical_float(value).parse::<f64>().unwrap(), value);
        }
    }

    #[test]
    fn truncation_rejects_out_of_range() {
        assert_eq!(truncate_to_int(-2.7, "int()").unwrap(), -2);
        assert_eq!(truncate_to_int(2.7, "int()").unwrap(), 2);
        assert_eq!(truncate_to_int(1e19, "int()").unwrap_err().code, CONVERSION);
    }
}
