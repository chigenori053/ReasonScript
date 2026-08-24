//! Basic-block VM: executes `reason-computation-ir/0.1` Functions.
//!
//! Deliberately mirrors `frontend/computation_ir/interpreter.py`
//! instruction-for-instruction (same block-walk loop, same per-block
//! visit-count loop guard, same RT-* error codes). `call_tensor` is
//! dispatched to `crate::tensor_dispatch`, which forwards to
//! `reasonscript_tensor_core` for all 65 frozen Tensor Standard Functions,
//! including autograd and Tensor trace/metadata collection.
//! Vision and Reason Object calls are dispatched in-process to their Rust
//! libraries; no per-operation subprocess bridge remains on this path.

use std::cell::RefCell;
use std::collections::HashMap;
use std::path::{Component, Path, PathBuf};
use std::rc::Rc;

use crate::ir::{Block, Expr, Function, Instruction, Program, Terminator};
use crate::value::{from_json, to_json, RuntimeReasonObject, StructValue, Value};

#[derive(Debug)]
pub struct RuntimeError {
    pub code: String,
    pub message: String,
    pub source_location: Option<serde_json::Value>,
}

impl RuntimeError {
    pub fn new(code: &str, message: impl Into<String>) -> Self {
        RuntimeError {
            code: code.to_string(),
            message: message.into(),
            source_location: None,
        }
    }

    fn with_source_location(mut self, source_location: Option<&serde_json::Value>) -> Self {
        if self.source_location.is_none() {
            self.source_location = source_location.cloned();
        }
        self
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
    reason_objects: RefCell<HashMap<String, Value>>,
    reasoning_bindings: HashMap<String, Value>,
    loop_trace: RefCell<Vec<serde_json::Value>>,
    loop_frames: RefCell<HashMap<String, (i64, serde_json::Value)>>,
    trace_enabled: bool,
    tensor_trace: RefCell<Vec<serde_json::Value>>,
    vision_trace: RefCell<Vec<serde_json::Value>>,
    reasoning_trace: RefCell<Vec<serde_json::Value>>,
    resource_root: PathBuf,
    filesystem_read: bool,
    filesystem_write: bool,
    backend: String,
}

impl<'a> Vm<'a> {
    pub fn new(program: &'a Program) -> Self {
        Self::with_numeric_mode(
            program,
            reasonscript_tensor_core::NumericMode::CompatReference,
        )
    }

    /// Phase 9: selects `NumericMode::NativeFast` (real `f32` rounding
    /// plus the parallel/rayon op paths in `tensor_dispatch.rs`) instead
    /// of the default `CompatReference`. See `NumericMode`'s own doc
    /// comment for exactly what differs.
    pub fn with_numeric_mode(
        program: &'a Program,
        numeric_mode: reasonscript_tensor_core::NumericMode,
    ) -> Self {
        Self::with_runtime_context(
            program,
            numeric_mode,
            reasonscript_tensor_core::TensorPolicy::default(),
            std::env::current_dir().unwrap_or_else(|_| PathBuf::from(".")),
            true,
            true,
            false,
            "RuntimeReal".to_owned(),
        )
    }

    #[allow(clippy::too_many_arguments)]
    pub fn with_runtime_context(
        program: &'a Program,
        numeric_mode: reasonscript_tensor_core::NumericMode,
        tensor_policy: reasonscript_tensor_core::TensorPolicy,
        resource_root: PathBuf,
        filesystem_read: bool,
        filesystem_write: bool,
        trace_enabled: bool,
        backend: String,
    ) -> Self {
        let functions = program
            .functions
            .iter()
            .map(|function| (function.id.as_str(), function))
            .collect();
        let mut tensors = reasonscript_tensor_core::TensorStore::with_numeric_mode(numeric_mode);
        tensors.configure_context(
            tensor_policy,
            resource_root.clone(),
            filesystem_read,
            filesystem_write,
        );
        Vm {
            functions,
            max_loop_iterations: DEFAULT_MAX_LOOP_ITERATIONS,
            max_call_depth: DEFAULT_MAX_CALL_DEPTH,
            tensors: RefCell::new(tensors),
            reason_objects: RefCell::new(HashMap::new()),
            reasoning_bindings: program
                .reasoning_bindings
                .iter()
                .map(|(name, value)| (name.clone(), Value::String(Rc::from(value.as_str()))))
                .collect(),
            loop_trace: RefCell::new(Vec::new()),
            loop_frames: RefCell::new(HashMap::new()),
            trace_enabled,
            tensor_trace: RefCell::new(Vec::new()),
            vision_trace: RefCell::new(Vec::new()),
            reasoning_trace: RefCell::new(Vec::new()),
            resource_root,
            filesystem_read,
            filesystem_write,
            backend,
        }
    }

    pub fn loop_trace(&self) -> Vec<serde_json::Value> {
        self.loop_trace.borrow().clone()
    }

    pub fn tensor_trace(&self) -> Vec<serde_json::Value> {
        self.tensor_trace.borrow().clone()
    }

    pub fn tensor_metadata(&self) -> Vec<serde_json::Value> {
        self.tensors.borrow().metadata()
    }

    pub fn vision_trace(&self) -> Vec<serde_json::Value> {
        self.vision_trace.borrow().clone()
    }

    pub fn reasoning_trace(&self) -> Vec<serde_json::Value> {
        self.reasoning_trace.borrow().clone()
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
        let mut object_bindings = HashMap::new();
        if !program.reason_object_bindings.is_empty() && !self.filesystem_read {
            return Err(RuntimeError::new(
                "RUO-N2-007",
                "filesystem_read capability is required",
            ));
        }
        for binding in &program.reason_object_bindings {
            let source = Path::new(&binding.source_path);
            if source.is_absolute()
                || source.components().any(|part| {
                    matches!(
                        part,
                        Component::ParentDir | Component::RootDir | Component::Prefix(_)
                    )
                })
            {
                return Err(RuntimeError::new(
                    "RUO-N2-006",
                    "Object path escapes resource root",
                ));
            }
            let canonical_root = std::fs::canonicalize(&self.resource_root).map_err(|error| {
                RuntimeError::new("RUO-N2-013", format!("Object load failed: {error}"))
            })?;
            let resolved = std::fs::canonicalize(canonical_root.join(source)).map_err(|error| {
                RuntimeError::new("RUO-N2-013", format!("Object load failed: {error}"))
            })?;
            if !resolved.starts_with(&canonical_root) {
                return Err(RuntimeError::new(
                    "RUO-N2-006",
                    "Object path escapes resource root",
                ));
            }
            let object = reasonscript_native_reasonunit_runtime::load_ruo(&resolved)
                .map_err(|error| RuntimeError::new(&error.code, error.message))?;
            if let Some(expected) = &binding.expected_object_id {
                if object.object_id.as_str() != expected {
                    return Err(RuntimeError::new(
                        "RUO-N2-013",
                        "expected Object ID assertion failed",
                    ));
                }
            }
            object_bindings.insert(
                binding.name.clone(),
                Value::ReasonObject(Rc::new(RuntimeReasonObject {
                    object: RefCell::new(object),
                    source_path: resolved,
                    resource_root: self.resource_root.clone(),
                    filesystem_write: self.filesystem_write,
                })),
            );
        }
        *self.reason_objects.borrow_mut() = object_bindings;
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
            env.extend(self.reasoning_bindings.clone());
            env.extend(
                self.reason_objects
                    .borrow()
                    .iter()
                    .map(|(name, value)| (name.clone(), value.clone())),
            );
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
            self.collect_tensors(calculations.iter().map(|(_, value)| value));
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
                self.collect_tensors(env.values());
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

    fn collect_tensors<'v>(&self, values: impl Iterator<Item = &'v Value>) {
        let mut roots = std::collections::HashSet::new();
        for value in values {
            collect_tensor_ids(value, &mut roots);
        }
        self.tensors.borrow_mut().collect(&roots);
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
            Instruction::TraceLoopStart { loop_id, counter } => {
                let iteration = match env.get(counter) {
                    Some(Value::Int(value)) => *value + 1,
                    _ => {
                        return Err(RuntimeError::new(
                            "IR-EXEC-009",
                            "loop trace counter is missing",
                        ))
                    }
                };
                env.insert(counter.clone(), Value::Int(iteration));
                self.loop_frames
                    .borrow_mut()
                    .insert(loop_id.clone(), (iteration, trace_env(env)));
                Ok(())
            }
            Instruction::TraceLoopEnd {
                loop_id,
                break_triggered,
                continue_triggered,
            } => {
                let Some((iteration, previous_state)) =
                    self.loop_frames.borrow_mut().remove(loop_id)
                else {
                    return Err(RuntimeError::new(
                        "IR-EXEC-009",
                        "loop trace frame is missing",
                    ));
                };
                self.loop_trace.borrow_mut().push(serde_json::json!({
                    "loop_id": loop_id,
                    "iteration": iteration,
                    "condition": true,
                    "previous_state": previous_state,
                    "updated_state": trace_env(env),
                    "break_triggered": break_triggered,
                    "continue_triggered": continue_triggered,
                }));
                Ok(())
            }
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
        self.eval_expr_inner(expr, env, call_depth)
            .map_err(|error| error.with_source_location(expr.source_span()))
    }

    fn eval_expr_inner(
        &self,
        expr: &Expr,
        env: &mut HashMap<String, Value>,
        call_depth: u32,
    ) -> Result<Value, RuntimeError> {
        match expr {
            Expr::Const { kind, value, .. } => const_value(kind, value),
            Expr::Local { name, .. } => env.get(name).cloned().ok_or_else(|| {
                RuntimeError::new("RT-NAME-001", format!("unknown runtime name: {name}"))
            }),
            Expr::Array { elements, .. } => {
                let mut items = Vec::with_capacity(elements.len());
                for element in elements {
                    items.push(self.eval_expr(element, env, call_depth)?);
                }
                Ok(Value::Array(Rc::new(RefCell::new(items))))
            }
            Expr::Struct {
                type_name, fields, ..
            } => {
                let mut evaluated = HashMap::new();
                for (name, field_expr) in fields {
                    evaluated.insert(name.clone(), self.eval_expr(field_expr, env, call_depth)?);
                }
                Ok(Value::Struct(Rc::new(StructValue {
                    type_name: type_name.clone(),
                    fields: RefCell::new(evaluated),
                })))
            }
            Expr::Unary {
                operator, operand, ..
            } => {
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
                ..
            } => {
                let left_value = self.eval_expr(left, env, call_depth)?;
                let right_value = self.eval_expr(right, env, call_depth)?;
                eval_binary(operator, left_value, right_value)
            }
            Expr::Comparison {
                operator,
                left,
                right,
                ..
            } => {
                let left_value = self.eval_expr(left, env, call_depth)?;
                let right_value = self.eval_expr(right, env, call_depth)?;
                eval_comparison(operator, left_value, right_value)
            }
            Expr::Logical {
                operator,
                left,
                right,
                ..
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
            Expr::Index {
                collection, index, ..
            } => {
                let collection_value = self.eval_expr(collection, env, call_depth)?;
                let index_value = self.eval_expr(index, env, call_depth)?;
                index_value_lookup(collection_value, index_value)
            }
            Expr::Member { object, member, .. } => {
                let owner = self.eval_expr(object, env, call_depth)?;
                member_lookup(owner, member)
            }
            Expr::CallTensor {
                function_id,
                arguments,
                source_span,
            } => {
                let mut values = Vec::with_capacity(arguments.len());
                for argument in arguments {
                    values.push(self.eval_expr(argument, env, call_depth)?);
                }
                let result =
                    crate::tensor_dispatch::call(function_id, values.clone(), &self.tensors)
                        .map_err(|error| error.with_source_location(source_span.as_ref()))?;
                if self.trace_enabled {
                    let mut trace = self.tensor_trace.borrow_mut();
                    let ordinal = trace.len() + 1;
                    let inputs: Vec<_> = values
                        .iter()
                        .map(|value| tensor_trace_value(value, &self.tensors.borrow()))
                        .collect();
                    trace.push(serde_json::json!({
                        "step_id": format!("step_{ordinal:04}"),
                        "operation_type": "standard_function_call",
                        "function_id": function_id,
                        "inputs": inputs,
                        "output": tensor_trace_value(&result, &self.tensors.borrow()),
                        "status": "success",
                        "diagnostics": [],
                        "operation_id": format!("op_tensor_call_{ordinal:03}"),
                        "semantic_operation": function_id,
                        "lowered_operations": [function_id],
                        "source_ref": source_span,
                    }));
                }
                Ok(result)
            }
            Expr::CallVision {
                function_id,
                arguments,
                ..
            } => {
                let mut values = Vec::with_capacity(arguments.len());
                for argument in arguments {
                    values.push(self.eval_expr(argument, env, call_depth)?);
                }
                let (result, trace) = crate::vision_dispatch::call(
                    function_id,
                    &values,
                    &self.resource_root,
                    self.filesystem_read,
                    self.filesystem_write,
                )?;
                if self.trace_enabled {
                    self.vision_trace.borrow_mut().push(trace);
                }
                Ok(result)
            }
            Expr::CallRuo {
                function_id,
                arguments,
                ..
            } => {
                let mut values = Vec::with_capacity(arguments.len());
                for argument in arguments {
                    values.push(self.eval_expr(argument, env, call_depth)?);
                }
                crate::ruo_dispatch::call(function_id, values)
            }
            Expr::CallOptimizer {
                function_id,
                arguments,
                ..
            } => {
                let mut values = Vec::with_capacity(arguments.len());
                for argument in arguments {
                    values.push(self.eval_expr(argument, env, call_depth)?);
                }
                crate::optimizer_dispatch::call(function_id, values, &self.tensors)
            }
            Expr::CallReasoning {
                function_id,
                arguments,
                ..
            } => {
                let expression = arguments
                    .first()
                    .ok_or_else(|| RuntimeError::new("RV-5", "RuntimeCallArgumentCountMismatch"))?;
                let argument = self.eval_expr(expression, env, call_depth)?;
                let outcome = reasonscript_reasoning_core::execute(
                    function_id,
                    &to_json(&argument),
                    &self.backend,
                )
                .map_err(|error| RuntimeError::new(&error.code, error.message))?;
                if self.trace_enabled {
                    self.reasoning_trace.borrow_mut().push(outcome.trace);
                }
                Ok(Value::Json(Rc::new(outcome.value)))
            }
            Expr::CallRelation {
                function_id,
                arguments,
                ..
            } => {
                let mut values = Vec::with_capacity(arguments.len());
                for argument in arguments {
                    values.push(self.eval_expr(argument, env, call_depth)?);
                }
                crate::relation_dispatch::call(function_id, values)
            }
            Expr::CallArrayAppend {
                collection, item, ..
            } => {
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
            Expr::CallCast { name, argument, .. } => {
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
            Expr::CallFunction {
                name, arguments, ..
            } => self.call_function(name, arguments, env, call_depth),
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
        let mut local_env: HashMap<String, Value> = self.reason_objects.borrow().clone();
        local_env.extend(self.reasoning_bindings.clone());
        local_env.extend(function.parameters.iter().cloned().zip(arguments));
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

fn trace_env(env: &HashMap<String, Value>) -> serde_json::Value {
    let mut visible = std::collections::BTreeMap::new();
    for (name, value) in env {
        if name.starts_with("__for_") || name.starts_with("__trace_") {
            continue;
        }
        visible.insert(name.clone(), to_json(value));
    }
    serde_json::to_value(visible).expect("trace environment is JSON-compatible")
}

fn tensor_trace_value(
    value: &Value,
    store: &reasonscript_tensor_core::TensorStore,
) -> serde_json::Value {
    match value {
        Value::Tensor(id) => store
            .tensor_info(id)
            .unwrap_or_else(|| serde_json::json!({"tensor_id": id.as_ref()})),
        Value::Array(items) => serde_json::Value::Array(
            items
                .borrow()
                .iter()
                .map(|item| tensor_trace_value(item, store))
                .collect(),
        ),
        _ => to_json(value),
    }
}

fn collect_tensor_ids(value: &Value, roots: &mut std::collections::HashSet<String>) {
    match value {
        Value::Tensor(id) => {
            roots.insert(id.to_string());
        }
        Value::Array(items) => {
            for item in items.borrow().iter() {
                collect_tensor_ids(item, roots);
            }
        }
        Value::Struct(value) => {
            for item in value.fields.borrow().values() {
                collect_tensor_ids(item, roots);
            }
        }
        _ => {}
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

pub(crate) fn eval_comparison(
    operator: &str,
    left: Value,
    right: Value,
) -> Result<Value, RuntimeError> {
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
        Value::Json(value) => value
            .as_object()
            .and_then(|values| values.get(member))
            .cloned()
            .map(from_json)
            .ok_or_else(|| RuntimeError::new("RT-FIELD-001", format!("unknown field {member}"))),
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
    fn tensor_softmax_executes_in_rust() {
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
                            "op": "call_tensor", "function_id": "tensor.to_array", "arguments": [{
                                "op": "call_tensor", "function_id": "tensor.softmax", "arguments": [{
                                    "op": "call_tensor", "function_id": "tensor.create", "arguments": [{
                                        "op": "array", "elements": [
                                            {"op": "const", "kind": "float", "value": 1.0},
                                            {"op": "const", "kind": "float", "value": 2.0}
                                        ]
                                    }, {"op": "const", "kind": "string", "value": "f64"}]
                                }]
                            }]
                        }
                    }
                }]
            }]
        }"#;
        let results = run(ir).expect("softmax should execute");
        let values = match &results[0].1 {
            Value::Array(values) => values.borrow(),
            _ => panic!("softmax array"),
        };
        let first = match values[0] {
            Value::Float(value) => value,
            _ => panic!("softmax float"),
        };
        assert!((first - 0.2689414213699951).abs() < 1e-12);
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
