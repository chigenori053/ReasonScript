//! Basic-block VM: executes `reason-computation-ir/0.1` Functions.
//!
//! Deliberately mirrors `frontend/computation_ir/interpreter.py`
//! instruction-for-instruction (same block-walk loop, same per-block
//! visit-count loop guard, same RT-* error codes). `call_tensor` is
//! dispatched to `crate::tensor_dispatch`, which forwards to
//! `reasonscript_tensor_core` (Phase 4) for the ~50 Tensor Standard
//! Functions it implements, and returns `RT-UNSUPPORTED-001` for the
//! rest (conv2d/pooling/softmax/relu/linear/autograd -- see
//! `tensor_dispatch.rs`'s module doc for the exact deferred list).
//! `call_vision` remains entirely unimplemented (out of scope).

use std::cell::RefCell;
use std::collections::HashMap;
use std::rc::Rc;

use crate::ir::{Block, Expr, Function, Instruction, Program, Terminator};
use crate::value::{StructValue, Value};

#[derive(Debug)]
pub struct RuntimeError {
    pub code: String,
    pub message: String,
}

impl RuntimeError {
    pub fn new(code: &str, message: impl Into<String>) -> Self {
        RuntimeError {
            code: code.to_string(),
            message: message.into(),
        }
    }
}

pub enum Outcome {
    Result(Value),
    Return(Value),
    NoValue,
}

const DEFAULT_MAX_LOOP_ITERATIONS: u64 = 10_000;
const DEFAULT_MAX_CALL_DEPTH: u32 = 128;

pub struct Vm<'a> {
    functions: HashMap<&'a str, &'a Function>,
    max_loop_iterations: u64,
    max_call_depth: u32,
    tensors: RefCell<reasonscript_tensor_core::TensorStore>,
}

impl<'a> Vm<'a> {
    pub fn new(program: &'a Program) -> Self {
        let functions = program
            .functions
            .iter()
            .map(|function| (function.id.as_str(), function))
            .collect();
        Vm {
            functions,
            max_loop_iterations: DEFAULT_MAX_LOOP_ITERATIONS,
            max_call_depth: DEFAULT_MAX_CALL_DEPTH,
            tensors: RefCell::new(reasonscript_tensor_core::TensorStore::new()),
        }
    }

    /// Executes every calculation in program order, mirroring
    /// `interpret_program`'s semantics: a calculation whose body falls
    /// off the end without `result =` simply contributes nothing (not an
    /// error), and each calculation's initial environment carries every
    /// prior calculation's result under its own name (matching
    /// `env = dict(calculations)` in both Python evaluators).
    pub fn run_calculations(
        &self,
        program: &Program,
    ) -> Result<Vec<(String, Value)>, RuntimeError> {
        let mut calculations: Vec<(String, Value)> = Vec::new();
        for calculation_id in &program.calculations {
            let function = *self.functions.get(calculation_id.as_str()).ok_or_else(|| {
                RuntimeError::new(
                    "RT-CALL-001",
                    format!("unknown calculation: {calculation_id}"),
                )
            })?;
            let mut env: HashMap<String, Value> = calculations
                .iter()
                .map(|(name, value)| (name.clone(), value.clone()))
                .collect();
            match self.run_function(function, &mut env, 0)? {
                Outcome::Result(value) => calculations.push((calculation_id.clone(), value)),
                Outcome::NoValue => {}
                Outcome::Return(_) => {
                    return Err(RuntimeError::new(
                        "IR-EXEC-005",
                        format!("calculation {calculation_id} used return instead of result"),
                    ))
                }
            }
        }
        Ok(calculations)
    }

    fn run_function(
        &self,
        function: &Function,
        env: &mut HashMap<String, Value>,
        call_depth: u32,
    ) -> Result<Outcome, RuntimeError> {
        let blocks: HashMap<&str, &Block> = function
            .blocks
            .iter()
            .map(|block| (block.id.as_str(), block))
            .collect();
        let mut current = function.entry_block.as_str();
        let mut visits: HashMap<String, u64> = HashMap::new();
        loop {
            let count = visits.entry(current.to_string()).or_insert(0);
            *count += 1;
            if *count > self.max_loop_iterations {
                return Err(RuntimeError::new(
                    "RT-LOOP-001",
                    format!(
                        "loop iteration limit exceeded: {}",
                        self.max_loop_iterations
                    ),
                ));
            }
            let block = blocks.get(current).ok_or_else(|| {
                RuntimeError::new("IR-EXEC-006", format!("unknown block: {current}"))
            })?;
            for instruction in &block.instructions {
                self.execute_instruction(instruction, env, call_depth)?;
            }
            match &block.terminator {
                Terminator::Jump { target } => {
                    current = self.resolve_block_id(&blocks, target)?;
                }
                Terminator::Branch {
                    condition,
                    then,
                    else_target,
                } => {
                    let condition_value = self.eval_expr(condition, env, call_depth)?;
                    let taken = match condition_value {
                        Value::Bool(value) => value,
                        other => {
                            return Err(RuntimeError::new(
                                "IR-EXEC-007",
                                format!("branch condition must be Bool, got {}", other.type_name()),
                            ))
                        }
                    };
                    current =
                        self.resolve_block_id(&blocks, if taken { then } else { else_target })?;
                }
                Terminator::Result { value } => {
                    return Ok(Outcome::Result(self.eval_expr(value, env, call_depth)?))
                }
                Terminator::Return { value } => {
                    return Ok(Outcome::Return(self.eval_expr(value, env, call_depth)?))
                }
                Terminator::Trap { code, message } => {
                    if code == "IR-NO-VALUE" {
                        return Ok(Outcome::NoValue);
                    }
                    return Err(RuntimeError::new(code, message.clone()));
                }
            }
        }
    }

    fn resolve_block_id<'b>(
        &self,
        blocks: &HashMap<&'b str, &'b Block>,
        target: &'b str,
    ) -> Result<&'b str, RuntimeError> {
        if blocks.contains_key(target) {
            Ok(target)
        } else {
            Err(RuntimeError::new(
                "IR-EXEC-006",
                format!("unknown block: {target}"),
            ))
        }
    }

    fn execute_instruction(
        &self,
        instruction: &Instruction,
        env: &mut HashMap<String, Value>,
        call_depth: u32,
    ) -> Result<(), RuntimeError> {
        match instruction {
            Instruction::Assign { target, expr } => {
                let value = self.eval_expr(expr, env, call_depth)?;
                env.insert(target.clone(), value);
                Ok(())
            }
            Instruction::Expr { expr } => {
                self.eval_expr(expr, env, call_depth)?;
                Ok(())
            }
            Instruction::IndexAssign {
                collection,
                index,
                expr,
            } => {
                let collection_value = self.eval_expr(collection, env, call_depth)?;
                let index_value = self.eval_expr(index, env, call_depth)?;
                let new_value = self.eval_expr(expr, env, call_depth)?;
                match collection_value {
                    Value::Array(items) => {
                        let index_int = match index_value {
                            Value::Int(value) => value,
                            _ => {
                                return Err(RuntimeError::new(
                                    "RT-INDEX-001",
                                    "array index must be int",
                                ))
                            }
                        };
                        let mut items = items.borrow_mut();
                        if index_int < 0 || index_int as usize >= items.len() {
                            return Err(RuntimeError::new(
                                "RT-INDEX-002",
                                format!("index out of range: {index_int}"),
                            ));
                        }
                        items[index_int as usize] = new_value;
                        Ok(())
                    }
                    _ => Err(RuntimeError::new(
                        "RT-INDEX-003",
                        "value is not mutable by index",
                    )),
                }
            }
            Instruction::FieldAssign {
                object,
                member,
                expr,
            } => {
                let owner = self.eval_expr(object, env, call_depth)?;
                let new_value = self.eval_expr(expr, env, call_depth)?;
                match owner {
                    Value::Struct(struct_value) => {
                        let mut fields = struct_value.fields.borrow_mut();
                        if !fields.contains_key(member) {
                            return Err(RuntimeError::new(
                                "RT-FIELD-002",
                                "invalid field assignment target",
                            ));
                        }
                        fields.insert(member.clone(), new_value);
                        Ok(())
                    }
                    _ => Err(RuntimeError::new(
                        "RT-FIELD-002",
                        "invalid field assignment target",
                    )),
                }
            }
        }
    }

    fn eval_expr(
        &self,
        expr: &Expr,
        env: &mut HashMap<String, Value>,
        call_depth: u32,
    ) -> Result<Value, RuntimeError> {
        match expr {
            Expr::Const { kind, value } => const_value(kind, value),
            Expr::Local { name } => env.get(name).cloned().ok_or_else(|| {
                RuntimeError::new("RT-NAME-001", format!("unknown runtime name: {name}"))
            }),
            Expr::Array { elements } => {
                let mut items = Vec::with_capacity(elements.len());
                for element in elements {
                    items.push(self.eval_expr(element, env, call_depth)?);
                }
                Ok(Value::Array(Rc::new(RefCell::new(items))))
            }
            Expr::Struct { type_name, fields } => {
                let mut evaluated = HashMap::new();
                for (name, field_expr) in fields {
                    evaluated.insert(name.clone(), self.eval_expr(field_expr, env, call_depth)?);
                }
                Ok(Value::Struct(Rc::new(StructValue {
                    type_name: type_name.clone(),
                    fields: RefCell::new(evaluated),
                })))
            }
            Expr::Unary { operator, operand } => {
                let value = self.eval_expr(operand, env, call_depth)?;
                match (operator.as_str(), value) {
                    ("Negate", Value::Int(v)) => Ok(Value::Int(-v)),
                    ("Negate", Value::Float(v)) => Ok(Value::Float(-v)),
                    ("Not", Value::Bool(v)) => Ok(Value::Bool(!v)),
                    (op, other) => Err(RuntimeError::new(
                        "RT-TYPE-001",
                        format!("unary {op} is not defined for {}", other.type_name()),
                    )),
                }
            }
            Expr::Binary {
                operator,
                left,
                right,
            } => {
                let left_value = self.eval_expr(left, env, call_depth)?;
                let right_value = self.eval_expr(right, env, call_depth)?;
                eval_binary(operator, left_value, right_value)
            }
            Expr::Comparison {
                operator,
                left,
                right,
            } => {
                let left_value = self.eval_expr(left, env, call_depth)?;
                let right_value = self.eval_expr(right, env, call_depth)?;
                eval_comparison(operator, left_value, right_value)
            }
            Expr::Logical {
                operator,
                left,
                right,
            } => {
                let left_value = as_bool(self.eval_expr(left, env, call_depth)?)?;
                if operator == "And" {
                    if !left_value {
                        return Ok(Value::Bool(false));
                    }
                } else if left_value {
                    return Ok(Value::Bool(true));
                }
                let right_value = as_bool(self.eval_expr(right, env, call_depth)?)?;
                Ok(Value::Bool(right_value))
            }
            Expr::Index { collection, index } => {
                let collection_value = self.eval_expr(collection, env, call_depth)?;
                let index_value = self.eval_expr(index, env, call_depth)?;
                index_value_lookup(collection_value, index_value)
            }
            Expr::Member { object, member } => {
                let owner = self.eval_expr(object, env, call_depth)?;
                member_lookup(owner, member)
            }
            Expr::CallTensor {
                function_id,
                arguments,
            } => {
                let mut values = Vec::with_capacity(arguments.len());
                for argument in arguments {
                    values.push(self.eval_expr(argument, env, call_depth)?);
                }
                crate::tensor_dispatch::call(function_id, values, &self.tensors)
            }
            Expr::CallVision { function_id, .. } => Err(RuntimeError::new(
                "RT-UNSUPPORTED-001",
                format!(
                    "{function_id}: vision execution is not implemented in the Phase 3 Rust VM"
                ),
            )),
            Expr::CallOptimizer {
                function_id,
                arguments,
            } => {
                let mut values = Vec::with_capacity(arguments.len());
                for argument in arguments {
                    values.push(self.eval_expr(argument, env, call_depth)?);
                }
                crate::optimizer_dispatch::call(function_id, values, &self.tensors)
            }
            Expr::CallArrayAppend { collection, item } => {
                let collection_value = self.eval_expr(collection, env, call_depth)?;
                let item_value = self.eval_expr(item, env, call_depth)?;
                match collection_value {
                    Value::Array(items) => {
                        let mut new_items = items.borrow().clone();
                        new_items.push(item_value.deep_clone());
                        Ok(Value::Array(Rc::new(RefCell::new(new_items))))
                    }
                    other => Err(RuntimeError::new(
                        "RT-CALL-002",
                        format!(
                            "array.append first argument must be an array, got {}",
                            other.type_name()
                        ),
                    )),
                }
            }
            Expr::CallCast { name, argument } => {
                let value = self.eval_expr(argument, env, call_depth)?;
                let numeric = match value {
                    Value::Int(v) => v as f64,
                    Value::Float(v) => v,
                    other => {
                        return Err(RuntimeError::new(
                            "RT-CALL-005",
                            format!(
                                "{name}() argument must be Int or Float, got {}",
                                other.type_name()
                            ),
                        ))
                    }
                };
                if name == "float" {
                    Ok(Value::Float(numeric))
                } else {
                    Ok(Value::Int(numeric.trunc() as i64))
                }
            }
            Expr::CallFunction { name, arguments } => {
                self.call_function(name, arguments, env, call_depth)
            }
        }
    }

    fn call_function(
        &self,
        name: &str,
        argument_exprs: &[Expr],
        env: &mut HashMap<String, Value>,
        call_depth: u32,
    ) -> Result<Value, RuntimeError> {
        let function_id = format!("fn.{name}");
        let function = *self.functions.get(function_id.as_str()).ok_or_else(|| {
            RuntimeError::new("RT-CALL-001", format!("unknown runtime function: {name}"))
        })?;
        if argument_exprs.len() != function.parameters.len() {
            return Err(RuntimeError::new(
                "RT-CALL-002",
                format!("function argument count mismatch: {name}"),
            ));
        }
        if call_depth >= self.max_call_depth {
            return Err(RuntimeError::new(
                "RT-CALL-003",
                format!("function call depth exceeded: {}", self.max_call_depth),
            ));
        }
        let mut arguments = Vec::with_capacity(argument_exprs.len());
        for argument_expr in argument_exprs {
            arguments.push(self.eval_expr(argument_expr, env, call_depth)?);
        }
        let mut local_env: HashMap<String, Value> =
            function.parameters.iter().cloned().zip(arguments).collect();
        match self.run_function(function, &mut local_env, call_depth + 1)? {
            Outcome::Return(value) => Ok(value),
            Outcome::NoValue => Err(RuntimeError::new(
                "RT-CALL-004",
                format!("function returned no value: {name}"),
            )),
            Outcome::Result(_) => Err(RuntimeError::new(
                "IR-EXEC-005",
                format!("function {name} used result instead of return"),
            )),
        }
    }
}

fn const_value(kind: &str, value: &serde_json::Value) -> Result<Value, RuntimeError> {
    match kind {
        "int" => value
            .as_i64()
            .map(Value::Int)
            .ok_or_else(|| RuntimeError::new("IR-EXEC-008", "malformed int constant")),
        "float" => value
            .as_f64()
            .map(Value::Float)
            .ok_or_else(|| RuntimeError::new("IR-EXEC-008", "malformed float constant")),
        "bool" => value
            .as_bool()
            .map(Value::Bool)
            .ok_or_else(|| RuntimeError::new("IR-EXEC-008", "malformed bool constant")),
        "string" => value
            .as_str()
            .map(|text| Value::String(Rc::from(text)))
            .ok_or_else(|| RuntimeError::new("IR-EXEC-008", "malformed string constant")),
        "null" => Ok(Value::Null),
        other => Err(RuntimeError::new(
            "IR-EXEC-008",
            format!("unknown const kind: {other}"),
        )),
    }
}

fn as_bool(value: Value) -> Result<bool, RuntimeError> {
    match value {
        Value::Bool(value) => Ok(value),
        other => Err(RuntimeError::new(
            "RT-TYPE-001",
            format!("expected Bool, got {}", other.type_name()),
        )),
    }
}

fn eval_binary(operator: &str, left: Value, right: Value) -> Result<Value, RuntimeError> {
    if matches!(operator, "Divide" | "Modulo") {
        let is_zero = match &right {
            Value::Int(0) => true,
            Value::Float(value) => *value == 0.0,
            _ => false,
        };
        if is_zero {
            return Err(RuntimeError::new(
                "RT-ARITH-001",
                "division or modulo by zero",
            ));
        }
    }
    match (operator, left, right) {
        ("Add", Value::Int(a), Value::Int(b)) => Ok(Value::Int(a + b)),
        ("Add", Value::Float(a), Value::Float(b)) => Ok(Value::Float(a + b)),
        ("Subtract", Value::Int(a), Value::Int(b)) => Ok(Value::Int(a - b)),
        ("Subtract", Value::Float(a), Value::Float(b)) => Ok(Value::Float(a - b)),
        ("Multiply", Value::Int(a), Value::Int(b)) => Ok(Value::Int(a * b)),
        ("Multiply", Value::Float(a), Value::Float(b)) => Ok(Value::Float(a * b)),
        // `/` always performs true division at runtime on the Python
        // side (Int / Int -> Float too), matching the L-006 type-checker
        // fix in frontend/language_surface/validation.py.
        ("Divide", Value::Int(a), Value::Int(b)) => Ok(Value::Float(a as f64 / b as f64)),
        ("Divide", Value::Float(a), Value::Float(b)) => Ok(Value::Float(a / b)),
        // Python's `%` is floor-modulo (result takes the sign of the
        // divisor), unlike Rust's `%` (truncating remainder, sign of the
        // dividend) -- rem_euclid-with-sign-correction reproduces it.
        ("Modulo", Value::Int(a), Value::Int(b)) => Ok(Value::Int(python_mod_i64(a, b))),
        ("Modulo", Value::Float(a), Value::Float(b)) => Ok(Value::Float(python_mod_f64(a, b))),
        (op, left, right) => Err(RuntimeError::new(
            "RT-TYPE-001",
            format!(
                "{op} is not defined for {} and {}",
                left.type_name(),
                right.type_name()
            ),
        )),
    }
}

fn python_mod_i64(a: i64, b: i64) -> i64 {
    let remainder = a % b;
    if remainder != 0 && (remainder < 0) != (b < 0) {
        remainder + b
    } else {
        remainder
    }
}

fn python_mod_f64(a: f64, b: f64) -> f64 {
    let remainder = a % b;
    if remainder != 0.0 && (remainder < 0.0) != (b < 0.0) {
        remainder + b
    } else {
        remainder
    }
}

fn eval_comparison(operator: &str, left: Value, right: Value) -> Result<Value, RuntimeError> {
    if operator == "Equal" {
        return Ok(Value::Bool(left == right));
    }
    if operator == "NotEqual" {
        return Ok(Value::Bool(left != right));
    }
    let ordering = match (&left, &right) {
        (Value::Int(a), Value::Int(b)) => a.partial_cmp(b),
        (Value::Float(a), Value::Float(b)) => a.partial_cmp(b),
        (Value::String(a), Value::String(b)) => a.partial_cmp(b),
        _ => {
            return Err(RuntimeError::new(
                "RT-TYPE-001",
                format!(
                    "{operator} is not defined for {} and {}",
                    left.type_name(),
                    right.type_name()
                ),
            ))
        }
    };
    let ordering = ordering.ok_or_else(|| {
        RuntimeError::new("RT-TYPE-001", format!("{operator} comparison is undefined"))
    })?;
    let result = match operator {
        "GreaterThan" => ordering.is_gt(),
        "GreaterThanOrEqual" => ordering.is_ge(),
        "LessThan" => ordering.is_lt(),
        "LessThanOrEqual" => ordering.is_le(),
        other => {
            return Err(RuntimeError::new(
                "IR-EXEC-009",
                format!("unknown comparison operator: {other}"),
            ))
        }
    };
    Ok(Value::Bool(result))
}

fn index_value_lookup(collection: Value, index: Value) -> Result<Value, RuntimeError> {
    match collection {
        Value::Array(items) => {
            let index_int = match index {
                Value::Int(value) => value,
                _ => return Err(RuntimeError::new("RT-INDEX-001", "array index must be int")),
            };
            let items = items.borrow();
            if index_int < 0 || index_int as usize >= items.len() {
                return Err(RuntimeError::new(
                    "RT-INDEX-002",
                    format!("index out of range: {index_int}"),
                ));
            }
            Ok(items[index_int as usize].clone())
        }
        _ => Err(RuntimeError::new("RT-INDEX-003", "value is not indexable")),
    }
}

fn member_lookup(owner: Value, member: &str) -> Result<Value, RuntimeError> {
    match owner {
        Value::Struct(struct_value) => struct_value
            .fields
            .borrow()
            .get(member)
            .cloned()
            .ok_or_else(|| {
                RuntimeError::new(
                    "RT-FIELD-001",
                    format!("unknown field {member} on {}", struct_value.type_name),
                )
            }),
        Value::Array(items) if member == "length" => Ok(Value::Int(items.borrow().len() as i64)),
        other => Err(RuntimeError::new(
            "RT-FIELD-001",
            format!(
                "member access is unsupported: {member} on {}",
                other.type_name()
            ),
        )),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::ir::decode;

    #[test]
    fn python_mod_matches_python_floor_semantics() {
        // Python: 7 % 3 == 1, -7 % 3 == 2, 7 % -3 == -2, -7 % -3 == -1
        assert_eq!(python_mod_i64(7, 3), 1);
        assert_eq!(python_mod_i64(-7, 3), 2);
        assert_eq!(python_mod_i64(7, -3), -2);
        assert_eq!(python_mod_i64(-7, -3), -1);
    }

    fn run(source: &str) -> Result<Vec<(String, Value)>, RuntimeError> {
        let program = decode(source).expect("valid IR JSON");
        let vm = Vm::new(&program);
        vm.run_calculations(&program)
    }

    #[test]
    fn integer_division_by_int_is_float() {
        let ir = r#"{
            "schema": "reason-computation-ir/0.1",
            "calculations": ["Answer"],
            "functions": [{
                "id": "Answer",
                "parameters": [],
                "entry_block": "b1",
                "blocks": [{
                    "id": "b1",
                    "instructions": [],
                    "terminator": {
                        "kind": "result",
                        "value": {
                            "op": "binary", "operator": "Divide",
                            "left": {"op": "const", "kind": "int", "value": 7},
                            "right": {"op": "const", "kind": "int", "value": 2}
                        }
                    }
                }]
            }]
        }"#;
        let results = run(ir).expect("no runtime error");
        assert_eq!(results, vec![("Answer".to_string(), Value::Float(3.5))]);
    }

    #[test]
    fn division_by_zero_reports_rt_arith_001() {
        let ir = r#"{
            "schema": "reason-computation-ir/0.1",
            "calculations": ["Answer"],
            "functions": [{
                "id": "Answer",
                "parameters": [],
                "entry_block": "b1",
                "blocks": [{
                    "id": "b1",
                    "instructions": [],
                    "terminator": {
                        "kind": "result",
                        "value": {
                            "op": "binary", "operator": "Divide",
                            "left": {"op": "const", "kind": "int", "value": 1},
                            "right": {"op": "const", "kind": "int", "value": 0}
                        }
                    }
                }]
            }]
        }"#;
        let error = run(ir).expect_err("must fail");
        assert_eq!(error.code, "RT-ARITH-001");
    }

    #[test]
    fn calculation_without_result_contributes_nothing() {
        let ir = r#"{
            "schema": "reason-computation-ir/0.1",
            "calculations": ["Answer"],
            "functions": [{
                "id": "Answer",
                "parameters": [],
                "entry_block": "b1",
                "blocks": [{
                    "id": "b1",
                    "instructions": [{
                        "op": "assign", "target": "x",
                        "expr": {"op": "const", "kind": "int", "value": 1}
                    }],
                    "terminator": {
                        "kind": "trap", "code": "IR-NO-VALUE", "message": "no result"
                    }
                }]
            }]
        }"#;
        let results = run(ir).expect("no runtime error");
        assert!(results.is_empty());
    }

    #[test]
    fn tensor_softmax_reports_unsupported_rather_than_panicking() {
        // tensor.create etc. are implemented (Phase 4); tensor.softmax is
        // deliberately still out of scope (see tensor_dispatch.rs's
        // module doc for the exact deferred list) and must report
        // RT-UNSUPPORTED-001 rather than panicking or being silently
        // wrong.
        let ir = r#"{
            "schema": "reason-computation-ir/0.1",
            "calculations": ["Answer"],
            "functions": [{
                "id": "Answer",
                "parameters": [],
                "entry_block": "b1",
                "blocks": [{
                    "id": "b1",
                    "instructions": [],
                    "terminator": {
                        "kind": "result",
                        "value": {
                            "op": "call_tensor", "function_id": "tensor.softmax", "arguments": []
                        }
                    }
                }]
            }]
        }"#;
        let error = run(ir).expect_err("must fail");
        assert_eq!(error.code, "RT-UNSUPPORTED-001");
    }

    #[test]
    fn tensor_create_and_to_array_round_trip() {
        let ir = r#"{
            "schema": "reason-computation-ir/0.1",
            "calculations": ["Answer"],
            "functions": [{
                "id": "Answer",
                "parameters": [],
                "entry_block": "b1",
                "blocks": [{
                    "id": "b1",
                    "instructions": [{
                        "op": "assign", "target": "a",
                        "expr": {
                            "op": "call_tensor", "function_id": "tensor.create",
                            "arguments": [
                                {"op": "array", "elements": [
                                    {"op": "const", "kind": "float", "value": 1.0},
                                    {"op": "const", "kind": "float", "value": 2.0}
                                ]},
                                {"op": "const", "kind": "string", "value": "f64"}
                            ]
                        }
                    }],
                    "terminator": {
                        "kind": "result",
                        "value": {
                            "op": "call_tensor", "function_id": "tensor.to_array",
                            "arguments": [{"op": "local", "name": "a"}]
                        }
                    }
                }]
            }]
        }"#;
        let results = run(ir).expect("no runtime error");
        assert_eq!(results.len(), 1);
        match &results[0].1 {
            Value::Array(items) => {
                let items = items.borrow();
                assert_eq!(items.len(), 2);
                assert_eq!(items[0], Value::Float(1.0));
                assert_eq!(items[1], Value::Float(2.0));
            }
            other => panic!("expected an array, got {other:?}"),
        }
    }

    #[test]
    fn array_index_out_of_range_reports_rt_index_002() {
        let ir = r#"{
            "schema": "reason-computation-ir/0.1",
            "calculations": ["Answer"],
            "functions": [{
                "id": "Answer",
                "parameters": [],
                "entry_block": "b1",
                "blocks": [{
                    "id": "b1",
                    "instructions": [],
                    "terminator": {
                        "kind": "result",
                        "value": {
                            "op": "index",
                            "collection": {"op": "array", "elements": [
                                {"op": "const", "kind": "int", "value": 1}
                            ]},
                            "index": {"op": "const", "kind": "int", "value": 5}
                        }
                    }
                }]
            }]
        }"#;
        let error = run(ir).expect_err("must fail");
        assert_eq!(error.code, "RT-INDEX-002");
    }
}
