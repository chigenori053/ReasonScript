#[derive(Debug, Clone, PartialEq)]
pub struct Symbol(pub String);

#[derive(Debug, Clone, PartialEq)]
pub struct State(pub String);

#[derive(Debug, Clone, PartialEq)]
pub struct Proof(pub String);

#[derive(Debug, Clone, PartialEq)]
pub enum Value {
    Symbol(Symbol),
    Nat(u64),
    Int(i64),
    Rational(i64, u64),
}

#[derive(Debug, Clone, PartialEq)]
pub enum BinaryOp {
    Add(Value, Value),
    Sub(Value, Value),
}

#[derive(Debug, Clone, PartialEq)]
pub enum Statement {
    Goal(Symbol),
    Derive(Symbol),
    Prove(Proof),
    Apply(Value),
    Compute(BinaryOp),
    Converge(Symbol),
    Rollback(State),
}

#[derive(Debug, Clone, PartialEq)]
pub struct Program {
    pub statements: Vec<Statement>,
}
