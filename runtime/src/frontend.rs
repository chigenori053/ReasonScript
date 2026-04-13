use crate::ast::*;
use crate::hir::*;

pub fn lower(program: &Program) -> HirProgram {
    let mut nodes = Vec::new();

    for stmt in &program.statements {
        match stmt {
            Statement::Goal(Symbol(s)) => {
                nodes.push(HirNode::Goal(s.clone()))
            }
            Statement::Apply(v) => {
                nodes.push(HirNode::Apply(render_value(v)))
            }
            Statement::Prove(Proof(p)) => {
                nodes.push(HirNode::Prove(p.clone()))
            }
            Statement::Converge(Symbol(s)) => {
                nodes.push(HirNode::Converge(s.clone()))
            }
            Statement::Rollback(State(s)) => {
                nodes.push(HirNode::Rollback(s.clone()))
            }
            Statement::Compute(BinaryOp::Add(a, b)) => {
                nodes.push(HirNode::ComputeAdd(render_value(a), render_value(b)))
            }
            Statement::Compute(BinaryOp::Sub(a, b)) => {
                nodes.push(HirNode::ComputeSub(render_value(a), render_value(b)))
            }
            _ => {}
        }
    }

    HirProgram { nodes }
}

fn render_value(value: &Value) -> String {
    match value {
        Value::Symbol(Symbol(symbol)) => symbol.clone(),
        Value::Nat(value) => value.to_string(),
        Value::Int(value) => value.to_string(),
        Value::Rational(numerator, denominator) => format!("{numerator}/{denominator}"),
    }
}
