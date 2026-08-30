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
    #[serde(default)]
    pub reason_object_bindings: Vec<ReasonObjectBinding>,
    #[serde(default)]
    pub reasoning_bindings: BTreeMap<String, String>,
}

#[derive(Debug, Deserialize)]
pub struct ReasonObjectBinding {
    pub name: String,
    pub source_path: String,
    #[serde(default)]
    pub expected_object_id: Option<String>,
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
    #[serde(rename = "trace_loop_start")]
    TraceLoopStart { loop_id: String, counter: String },
    #[serde(rename = "trace_loop_end")]
    TraceLoopEnd {
        loop_id: String,
        break_triggered: bool,
        continue_triggered: bool,
    },
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
    #[serde(rename = "pattern_branch")]
    PatternBranch {
        value: Expr,
        pattern: Pattern,
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
#[serde(tag = "kind")]
pub enum Pattern {
    #[serde(rename = "wildcard")]
    Wildcard,
    #[serde(rename = "binding")]
    Binding { name: String },
    #[serde(rename = "literal")]
    Literal {
        value_kind: String,
        value: serde_json::Value,
    },
    #[serde(rename = "range")]
    Range {
        lower: serde_json::Value,
        upper: serde_json::Value,
        lower_inclusive: bool,
        upper_inclusive: bool,
    },
    #[serde(rename = "enum")]
    Enum {
        enum_name: String,
        variant_name: String,
    },
    #[serde(rename = "optional_none")]
    OptionalNone,
    #[serde(rename = "optional_some")]
    OptionalSome { pattern: Box<Pattern> },
    #[serde(rename = "struct")]
    Struct {
        type_name: String,
        fields: BTreeMap<String, Pattern>,
    },
    #[serde(rename = "or")]
    Or { alternatives: Vec<Pattern> },
}

#[derive(Debug, Deserialize)]
#[serde(tag = "op")]
pub enum Expr {
    #[serde(rename = "const")]
    Const {
        kind: String,
        value: serde_json::Value,
        #[serde(default)]
        source_span: Option<serde_json::Value>,
    },
    #[serde(rename = "local")]
    Local {
        name: String,
        #[serde(default)]
        source_span: Option<serde_json::Value>,
    },
    #[serde(rename = "array")]
    Array {
        elements: Vec<Expr>,
        #[serde(default)]
        source_span: Option<serde_json::Value>,
    },
    #[serde(rename = "struct")]
    Struct {
        type_name: String,
        fields: BTreeMap<String, Expr>,
        #[serde(default)]
        source_span: Option<serde_json::Value>,
    },
    #[serde(rename = "enum_value")]
    EnumValue {
        enum_name: String,
        variant_name: String,
        #[serde(default)]
        source_span: Option<serde_json::Value>,
    },
    #[serde(rename = "optional_some")]
    OptionalSome {
        value: Box<Expr>,
        #[serde(default)]
        source_span: Option<serde_json::Value>,
    },
    #[serde(rename = "optional_none")]
    OptionalNone {
        #[serde(default)]
        source_span: Option<serde_json::Value>,
    },
    #[serde(rename = "unary")]
    Unary {
        operator: String,
        operand: Box<Expr>,
        #[serde(default)]
        source_span: Option<serde_json::Value>,
    },
    #[serde(rename = "binary")]
    Binary {
        operator: String,
        left: Box<Expr>,
        right: Box<Expr>,
        #[serde(default)]
        source_span: Option<serde_json::Value>,
    },
    #[serde(rename = "comparison")]
    Comparison {
        operator: String,
        left: Box<Expr>,
        right: Box<Expr>,
        #[serde(default)]
        source_span: Option<serde_json::Value>,
    },
    #[serde(rename = "logical")]
    Logical {
        operator: String,
        left: Box<Expr>,
        right: Box<Expr>,
        #[serde(default)]
        source_span: Option<serde_json::Value>,
    },
    #[serde(rename = "index")]
    Index {
        collection: Box<Expr>,
        index: Box<Expr>,
        #[serde(default)]
        source_span: Option<serde_json::Value>,
    },
    #[serde(rename = "member")]
    Member {
        object: Box<Expr>,
        member: String,
        #[serde(default)]
        source_span: Option<serde_json::Value>,
    },
    #[serde(rename = "call_tensor")]
    CallTensor {
        function_id: String,
        arguments: Vec<Expr>,
        #[serde(default)]
        source_span: Option<serde_json::Value>,
    },
    #[serde(rename = "call_vision")]
    CallVision {
        function_id: String,
        arguments: Vec<Expr>,
        #[serde(default)]
        source_span: Option<serde_json::Value>,
    },
    #[serde(rename = "call_ruo")]
    CallRuo {
        function_id: String,
        arguments: Vec<Expr>,
        #[serde(default)]
        source_span: Option<serde_json::Value>,
    },
    #[serde(rename = "call_optimizer")]
    CallOptimizer {
        function_id: String,
        arguments: Vec<Expr>,
        #[serde(default)]
        source_span: Option<serde_json::Value>,
    },
    #[serde(rename = "call_relation")]
    CallRelation {
        function_id: String,
        arguments: Vec<Expr>,
        #[serde(default)]
        source_span: Option<serde_json::Value>,
    },
    #[serde(rename = "call_reasoning")]
    CallReasoning {
        function_id: String,
        arguments: Vec<Expr>,
        #[serde(default)]
        source_span: Option<serde_json::Value>,
    },
    #[serde(rename = "call_array_append")]
    CallArrayAppend {
        collection: Box<Expr>,
        item: Box<Expr>,
        #[serde(default)]
        source_span: Option<serde_json::Value>,
    },
    #[serde(rename = "call_array_concat")]
    CallArrayConcat {
        left: Box<Expr>,
        right: Box<Expr>,
        #[serde(default)]
        source_span: Option<serde_json::Value>,
    },
    #[serde(rename = "call_string")]
    CallString {
        function_id: String,
        arguments: Vec<Expr>,
        #[serde(default)]
        source_span: Option<serde_json::Value>,
    },
    #[serde(rename = "call_function")]
    CallFunction {
        name: String,
        arguments: Vec<Expr>,
        #[serde(default)]
        source_span: Option<serde_json::Value>,
    },
    #[serde(rename = "call_cast")]
    CallCast {
        name: String,
        argument: Box<Expr>,
        #[serde(default)]
        source_span: Option<serde_json::Value>,
    },
    #[serde(rename = "call_assert")]
    CallAssert {
        condition: Box<Expr>,
        #[serde(default)]
        source_span: Option<serde_json::Value>,
    },
    #[serde(rename = "call_assert_eq")]
    CallAssertEq {
        left: Box<Expr>,
        right: Box<Expr>,
        #[serde(default)]
        source_span: Option<serde_json::Value>,
    },
}

impl Expr {
    pub fn source_span(&self) -> Option<&serde_json::Value> {
        match self {
            Expr::Const { source_span, .. }
            | Expr::Local { source_span, .. }
            | Expr::Array { source_span, .. }
            | Expr::Struct { source_span, .. }
            | Expr::EnumValue { source_span, .. }
            | Expr::OptionalSome { source_span, .. }
            | Expr::OptionalNone { source_span, .. }
            | Expr::Unary { source_span, .. }
            | Expr::Binary { source_span, .. }
            | Expr::Comparison { source_span, .. }
            | Expr::Logical { source_span, .. }
            | Expr::Index { source_span, .. }
            | Expr::Member { source_span, .. }
            | Expr::CallTensor { source_span, .. }
            | Expr::CallVision { source_span, .. }
            | Expr::CallRuo { source_span, .. }
            | Expr::CallOptimizer { source_span, .. }
            | Expr::CallRelation { source_span, .. }
            | Expr::CallReasoning { source_span, .. }
            | Expr::CallArrayAppend { source_span, .. }
            | Expr::CallArrayConcat { source_span, .. }
            | Expr::CallString { source_span, .. }
            | Expr::CallFunction { source_span, .. }
            | Expr::CallCast { source_span, .. }
            | Expr::CallAssert { source_span, .. }
            | Expr::CallAssertEq { source_span, .. } => source_span.as_ref(),
        }
    }
}

pub fn decode(source: &str) -> Result<Program, serde_json::Error> {
    serde_json::from_str(source)
}
