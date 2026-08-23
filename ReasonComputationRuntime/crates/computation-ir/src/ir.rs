//! Decoder for `reason-computation-ir/0.1` JSON documents, as produced by
//! `frontend.computation_ir.lowering.lower_program` on the Python side.
//!
//! Field names and shapes here must stay in lockstep with
//! `frontend/computation_ir/schema.py` and `lowering.py` -- this is the
//! Rust side of the "Python frontend generates canonical JSON, Rust reads
//! it" transfer rule from the modernization plan (section 6).

use std::collections::BTreeMap;

use serde::Deserialize;

pub const SCHEMA: &str = "reason-computation-ir/0.1";

#[derive(Debug, Deserialize)]
pub struct Program {
    pub schema: String,
    #[serde(default)]
    pub package: Option<String>,
    pub calculations: Vec<String>,
    pub functions: Vec<Function>,
}

#[derive(Debug, Deserialize)]
pub struct Function {
    pub id: String,
    pub parameters: Vec<String>,
    pub entry_block: String,
    pub blocks: Vec<Block>,
}

#[derive(Debug, Deserialize)]
pub struct Block {
    pub id: String,
    pub instructions: Vec<Instruction>,
    pub terminator: Terminator,
}

#[derive(Debug, Deserialize)]
#[serde(tag = "op")]
pub enum Instruction {
    #[serde(rename = "assign")]
    Assign { target: String, expr: Expr },
    #[serde(rename = "index_assign")]
    IndexAssign {
        collection: Expr,
        index: Expr,
        expr: Expr,
    },
    #[serde(rename = "field_assign")]
    FieldAssign {
        object: Expr,
        member: String,
        expr: Expr,
    },
    #[serde(rename = "expr")]
    Expr { expr: Expr },
}

#[derive(Debug, Deserialize)]
#[serde(tag = "kind")]
pub enum Terminator {
    #[serde(rename = "jump")]
    Jump { target: String },
    #[serde(rename = "branch")]
    Branch {
        condition: Expr,
        then: String,
        #[serde(rename = "else")]
        else_target: String,
    },
    #[serde(rename = "result")]
    Result { value: Expr },
    #[serde(rename = "return")]
    Return { value: Expr },
    #[serde(rename = "trap")]
    Trap { code: String, message: String },
}

#[derive(Debug, Deserialize)]
#[serde(tag = "op")]
pub enum Expr {
    #[serde(rename = "const")]
    Const {
        kind: String,
        value: serde_json::Value,
    },
    #[serde(rename = "local")]
    Local { name: String },
    #[serde(rename = "array")]
    Array { elements: Vec<Expr> },
    #[serde(rename = "struct")]
    Struct {
        type_name: String,
        fields: BTreeMap<String, Expr>,
    },
    #[serde(rename = "unary")]
    Unary {
        operator: String,
        operand: Box<Expr>,
    },
    #[serde(rename = "binary")]
    Binary {
        operator: String,
        left: Box<Expr>,
        right: Box<Expr>,
    },
    #[serde(rename = "comparison")]
    Comparison {
        operator: String,
        left: Box<Expr>,
        right: Box<Expr>,
    },
    #[serde(rename = "logical")]
    Logical {
        operator: String,
        left: Box<Expr>,
        right: Box<Expr>,
    },
    #[serde(rename = "index")]
    Index {
        collection: Box<Expr>,
        index: Box<Expr>,
    },
    #[serde(rename = "member")]
    Member { object: Box<Expr>, member: String },
    #[serde(rename = "call_tensor")]
    CallTensor {
        function_id: String,
        arguments: Vec<Expr>,
    },
    #[serde(rename = "call_vision")]
    CallVision {
        function_id: String,
        arguments: Vec<Expr>,
    },
    #[serde(rename = "call_optimizer")]
    CallOptimizer {
        function_id: String,
        arguments: Vec<Expr>,
    },
    #[serde(rename = "call_relation")]
    CallRelation {
        function_id: String,
        arguments: Vec<Expr>,
    },
    #[serde(rename = "call_array_append")]
    CallArrayAppend {
        collection: Box<Expr>,
        item: Box<Expr>,
    },
    #[serde(rename = "call_function")]
    CallFunction { name: String, arguments: Vec<Expr> },
    #[serde(rename = "call_cast")]
    CallCast { name: String, argument: Box<Expr> },
}

pub fn decode(source: &str) -> Result<Program, serde_json::Error> {
    serde_json::from_str(source)
}
