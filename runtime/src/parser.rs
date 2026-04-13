use crate::ast::{BinaryOp, Program, Proof, State, Statement, Symbol, Value};

pub fn parse(source: &str) -> Program {
    let statements = source
        .lines()
        .filter_map(|line| {
            let line = line.trim();
            if line.is_empty() {
                return None;
            }
            let mut parts = line.splitn(2, ' ');
            let keyword = parts.next()?;
            let arg = parts.next().unwrap_or("").trim().to_string();
            match keyword {
                "goal" => Some(Statement::Goal(Symbol(arg))),
                "derive" => Some(Statement::Derive(Symbol(arg))),
                "prove" => Some(Statement::Prove(Proof(arg))),
                "apply" => Some(Statement::Apply(parse_value(&arg))),
                "compute" => parse_compute(&arg).map(Statement::Compute),
                "converge" => Some(Statement::Converge(Symbol(arg))),
                "rollback" => Some(Statement::Rollback(State(arg))),
                _ => None,
            }
        })
        .collect();

    Program { statements }
}

fn parse_value(input: &str) -> Value {
    if let Some((numerator, denominator)) = parse_rational(input) {
        return Value::Rational(numerator, denominator);
    }

    if let Ok(value) = input.parse::<i64>() {
        if input.starts_with('-') {
            return Value::Int(value);
        }
    }

    if let Ok(value) = input.parse::<u64>() {
        return Value::Nat(value);
    }

    Value::Symbol(Symbol(input.to_string()))
}

fn parse_rational(input: &str) -> Option<(i64, u64)> {
    let (numerator, denominator) = input.split_once('/')?;
    if denominator.is_empty() {
        return None;
    }

    let numerator = numerator.parse::<i64>().ok()?;
    let denominator = denominator.parse::<u64>().ok()?;
    Some((numerator, denominator))
}

fn parse_compute(input: &str) -> Option<BinaryOp> {
    let mut parts = input.split_whitespace();
    let left = parse_value(parts.next()?);
    let operator = parts.next()?;
    let right = parse_value(parts.next()?);

    if parts.next().is_some() {
        return None;
    }

    match operator {
        "+" => Some(BinaryOp::Add(left, right)),
        "-" => Some(BinaryOp::Sub(left, right)),
        _ => None,
    }
}
