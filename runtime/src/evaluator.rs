use crate::ast::{BinaryOp, Program, Statement, Value};

#[derive(Debug, Clone, PartialEq)]
pub struct ExecutionResult {
    pub trace: Vec<String>,
    pub current_state: String,
    pub previous_state: Option<String>,
    pub proof_failed: bool,
}

pub fn evaluate(program: &Program) -> ExecutionResult {
    let mut trace = Vec::new();
    let mut current_state = "INIT".to_string();
    let mut previous_state: Option<String> = None;
    let mut proof_failed = false;

    for stmt in &program.statements {
        match stmt {
            Statement::Goal(s) => trace.push(format!("GOAL: {}", s.0)),
            Statement::Derive(s) => trace.push(format!("DERIVE: {}", s.0)),
            Statement::Prove(p) => {
                if p.0.contains("invalid") {
                    proof_failed = true;
                    trace.push(format!("PROVE_FAIL: {}", p.0));
                    restore_previous_state(&previous_state, &mut current_state);
                    trace.push("ROLLBACK(auto)".to_string());
                } else {
                    trace.push(format!("PROVE: {}", p.0));
                }
            }
            Statement::Converge(s) => trace.push(format!("CONVERGE: {}", s.0)),
            Statement::Apply(value) => {
                let Some(rendered) = evaluate_value(value, &mut trace, &previous_state, &mut current_state, &mut proof_failed) else {
                    continue;
                };
                previous_state = Some(current_state.clone());
                current_state = rendered.clone();
                trace.push(format!("APPLY: {}", rendered));
            }
            Statement::Compute(operation) => {
                let Some(result) = evaluate_binary_op(operation, &mut trace, &previous_state, &mut current_state, &mut proof_failed) else {
                    continue;
                };
                previous_state = Some(current_state.clone());
                current_state = result.clone();
                trace.push(format!("COMPUTE: {}", result));
            }
            Statement::Rollback(st) => {
                restore_previous_state(&previous_state, &mut current_state);
                trace.push(format!("ROLLBACK: {}", st.0));
            }
        }
    }

    ExecutionResult {
        trace,
        current_state,
        previous_state,
        proof_failed,
    }
}

fn restore_previous_state(previous_state: &Option<String>, current_state: &mut String) {
    if let Some(safe) = previous_state {
        *current_state = safe.clone();
    }
}

fn evaluate_value(
    value: &Value,
    trace: &mut Vec<String>,
    previous_state: &Option<String>,
    current_state: &mut String,
    proof_failed: &mut bool,
) -> Option<String> {
    match normalize_value(value) {
        Some(normalized) => Some(render_value(&normalized)),
        None => {
            trigger_numeric_failure(trace, previous_state, current_state, proof_failed);
            None
        }
    }
}

fn evaluate_binary_op(
    operation: &BinaryOp,
    trace: &mut Vec<String>,
    previous_state: &Option<String>,
    current_state: &mut String,
    proof_failed: &mut bool,
) -> Option<String> {
    let computed = match operation {
        BinaryOp::Add(left, right) => add_values(left, right),
        BinaryOp::Sub(left, right) => sub_values(left, right),
    };

    match computed {
        Some(value) => Some(render_value(&value)),
        None => {
            trigger_numeric_failure(trace, previous_state, current_state, proof_failed);
            None
        }
    }
}

fn trigger_numeric_failure(
    trace: &mut Vec<String>,
    previous_state: &Option<String>,
    current_state: &mut String,
    proof_failed: &mut bool,
) {
    *proof_failed = true;
    trace.push("PROVE_FAIL: denominator_nonzero".to_string());
    restore_previous_state(previous_state, current_state);
    trace.push("ROLLBACK(auto)".to_string());
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

    let mut normalized_numerator = numerator;
    let mut normalized_denominator = denominator as i64;

    if normalized_denominator < 0 {
        normalized_numerator = -normalized_numerator;
        normalized_denominator = -normalized_denominator;
    }

    let divisor = gcd_i64(normalized_numerator.abs(), normalized_denominator.abs());
    Some(Value::Rational(
        normalized_numerator / divisor,
        (normalized_denominator / divisor) as u64,
    ))
}

fn gcd_i64(mut left: i64, mut right: i64) -> i64 {
    while right != 0 {
        let remainder = left % right;
        left = right;
        right = remainder;
    }
    left.abs()
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

    if is_rational_value(left) || is_rational_value(right) {
        return Some(normalized);
    }

    match normalized {
        Value::Rational(numerator, 1)
            if numerator >= 0 && is_nat_value(left) && is_nat_value(right) =>
        {
            Some(Value::Nat(numerator as u64))
        }
        Value::Rational(numerator, 1) => Some(Value::Int(numerator)),
        other => Some(other),
    }
}

fn is_nat_value(value: &Value) -> bool {
    matches!(value, Value::Nat(_))
}

fn is_rational_value(value: &Value) -> bool {
    matches!(value, Value::Rational(_, _))
}

fn render_value(value: &Value) -> String {
    match value {
        Value::Symbol(symbol) => symbol.0.clone(),
        Value::Nat(value) => value.to_string(),
        Value::Int(value) => value.to_string(),
        Value::Rational(numerator, denominator) => format!("{numerator}/{denominator}"),
    }
}
