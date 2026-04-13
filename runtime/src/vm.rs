use crate::ast::Value;
use crate::mir::{MirOp, MirProgram};

#[derive(Debug, Clone, PartialEq)]
pub struct VmResult {
    pub stack: Vec<String>,
    pub trace: Vec<String>,
    pub current_state: String,
    pub previous_state: Option<String>,
    pub proof_failed: bool,
}

pub fn execute(program: &MirProgram) -> VmResult {
    let mut stack = Vec::new();
    let mut trace = Vec::new();
    let mut current_state = "INIT".to_string();
    let mut previous_state = None;
    let mut proof_failed = false;

    for op in &program.ops {
        match op {
            MirOp::PushConst(value) => {
                stack.push(value.clone());
                current_state = value.clone();
                trace.push(format!("PUSH: {value}"));
            }
            MirOp::Add => {
                let Some(result) = execute_binary_op(&mut stack, add_values) else {
                    continue;
                };
                current_state = result.clone();
                trace.push("ADD".to_string());
            }
            MirOp::Sub => {
                let Some(result) = execute_binary_op(&mut stack, sub_values) else {
                    continue;
                };
                current_state = result.clone();
                trace.push("SUB".to_string());
            }
            MirOp::Checkpoint => {
                previous_state = stack.last().cloned();
                trace.push("CHECKPOINT".to_string());
            }
            MirOp::Rollback => {
                restore_checkpoint(&previous_state, &mut stack, &mut current_state);
                trace.push("ROLLBACK(vm)".to_string());
            }
            MirOp::ProofGuard(guard) => {
                if guard.contains("denominator_nonzero") && stack_top_has_zero_denominator(&stack) {
                    proof_failed = true;
                    trace.push("PROVE_FAIL: denominator_nonzero".to_string());
                    restore_checkpoint(&previous_state, &mut stack, &mut current_state);
                    trace.push("ROLLBACK(vm)".to_string());
                } else {
                    trace.push(format!("PROOF_GUARD: {guard}"));
                }
            }
            MirOp::Converge => trace.push("CONVERGE".to_string()),
        }
    }

    VmResult {
        stack,
        trace,
        current_state,
        previous_state,
        proof_failed,
    }
}

fn execute_binary_op(
    stack: &mut Vec<String>,
    op: fn(&Value, &Value) -> Option<Value>,
) -> Option<String> {
    let right = parse_scalar(&stack.pop()?)?;
    let left = parse_scalar(&stack.pop()?)?;
    let result = op(&left, &right)?;
    let rendered = render_value(&result);
    stack.push(rendered.clone());
    Some(rendered)
}

fn restore_checkpoint(
    previous_state: &Option<String>,
    stack: &mut Vec<String>,
    current_state: &mut String,
) {
    if let Some(saved) = previous_state {
        stack.clear();
        stack.push(saved.clone());
        *current_state = saved.clone();
    }
}

fn stack_top_has_zero_denominator(stack: &[String]) -> bool {
    let Some(top) = stack.last() else {
        return false;
    };

    matches!(parse_scalar(top), Some(Value::Rational(_, 0)))
}

fn parse_scalar(input: &str) -> Option<Value> {
    if let Some((numerator, denominator)) = input.split_once('/') {
        return Some(Value::Rational(
            numerator.parse::<i64>().ok()?,
            denominator.parse::<u64>().ok()?,
        ));
    }

    if input.starts_with('-') {
        if let Ok(value) = input.parse::<i64>() {
            return Some(Value::Int(value));
        }
    }

    if let Ok(value) = input.parse::<u64>() {
        return Some(Value::Nat(value));
    }

    Some(Value::Symbol(crate::ast::Symbol(input.to_string())))
}

fn add_values(left: &Value, right: &Value) -> Option<Value> {
    let (left_numerator, left_denominator) = as_rational_components(left)?;
    let (right_numerator, right_denominator) = as_rational_components(right)?;
    let denominator = left_denominator.checked_mul(right_denominator)?;
    let right_denominator = i64::try_from(right_denominator).ok()?;
    let left_denominator = i64::try_from(left_denominator).ok()?;
    let numerator = left_numerator * right_denominator + right_numerator * left_denominator;
    build_promoted_result(left, right, numerator, denominator)
}

fn sub_values(left: &Value, right: &Value) -> Option<Value> {
    let (left_numerator, left_denominator) = as_rational_components(left)?;
    let (right_numerator, right_denominator) = as_rational_components(right)?;
    let denominator = left_denominator.checked_mul(right_denominator)?;
    let right_denominator = i64::try_from(right_denominator).ok()?;
    let left_denominator = i64::try_from(left_denominator).ok()?;
    let numerator = left_numerator * right_denominator - right_numerator * left_denominator;
    build_promoted_result(left, right, numerator, denominator)
}

fn as_rational_components(value: &Value) -> Option<(i64, u64)> {
    match normalize_value(value)? {
        Value::Nat(value) => Some((value as i64, 1)),
        Value::Int(value) => Some((value, 1)),
        Value::Rational(numerator, denominator) => Some((numerator, denominator)),
        Value::Symbol(_) => None,
    }
}

fn build_promoted_result(
    left: &Value,
    right: &Value,
    numerator: i64,
    denominator: u64,
) -> Option<Value> {
    let normalized = normalize_rational(numerator, denominator)?;

    if matches!(left, Value::Rational(_, _)) || matches!(right, Value::Rational(_, _)) {
        return Some(normalized);
    }

    match normalized {
        Value::Rational(numerator, 1)
            if numerator >= 0 && matches!(left, Value::Nat(_)) && matches!(right, Value::Nat(_)) =>
        {
            Some(Value::Nat(numerator as u64))
        }
        Value::Rational(numerator, 1) => Some(Value::Int(numerator)),
        other => Some(other),
    }
}

fn normalize_value(value: &Value) -> Option<Value> {
    match value {
        Value::Symbol(symbol) => Some(Value::Symbol(symbol.clone())),
        Value::Nat(value) => Some(Value::Nat(*value)),
        Value::Int(value) => Some(Value::Int(*value)),
        Value::Rational(numerator, denominator) => normalize_rational(*numerator, *denominator),
    }
}

fn normalize_rational(numerator: i64, denominator: u64) -> Option<Value> {
    if denominator == 0 {
        return None;
    }

    if numerator == 0 {
        return Some(Value::Rational(0, 1));
    }

    let divisor = gcd_i64(numerator.abs(), denominator as i64);
    Some(Value::Rational(numerator / divisor, denominator / divisor as u64))
}

fn gcd_i64(mut left: i64, mut right: i64) -> i64 {
    while right != 0 {
        let remainder = left % right;
        left = right;
        right = remainder;
    }
    left.abs()
}

fn render_value(value: &Value) -> String {
    match value {
        Value::Symbol(symbol) => symbol.0.clone(),
        Value::Nat(value) => value.to_string(),
        Value::Int(value) => value.to_string(),
        Value::Rational(numerator, denominator) => format!("{numerator}/{denominator}"),
    }
}
