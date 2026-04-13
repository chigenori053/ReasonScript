#[derive(Debug, Clone, PartialEq)]
pub enum HirNode {
    Number(i64),
    Goal(String),
    Apply(String),
    ComputeAdd(String, String),
    ComputeSub(String, String),  
    Prove(String),
    Converge(String),
    Rollback(String),
}
#[derive(Debug, Clone, PartialEq)]
pub struct HirProgram {
    pub nodes: Vec<HirNode>,
}