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

use std::cell::{Cell, RefCell};
use std::collections::{HashMap, VecDeque};
use std::path::{Component, Path, PathBuf};
use std::rc::Rc;
use std::time::Instant;

use crate::candidate_space::{isqrt, Added, CandidateSpace, CmpOp, Constraint, Generator};
use crate::ir::{Block, Expr, Function, Instruction, Pattern, Program, Terminator};
use crate::state_trace::{TraceConfig, TraceMode, TraceState};
use crate::value::{from_json, to_json, FastMap, RuntimeReasonObject, StructValue, Value};

/// A frame's bindings. FxHash-keyed (see `value::FxHasher`).
pub type Env = FastMap<String, Value>;

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

/// Compiler/runtime contract default (Phase 4, "制御された再帰"):
/// overridable per request via `context.limits.max_call_depth`.
pub const DEFAULT_MAX_CALL_DEPTH: u32 = 128;

/// P0-2 Execution Budget. Replaces the former fixed 10,000-visit loop cap.
/// Every field is optional (`None`, or `0` in the request, = unlimited) and
/// comes from the request's `context.limits`. When several are exhausted the
/// spec's priority order decides the reported reason: wall time, memory,
/// VM instructions, reasoning steps, loop iterations.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct ExecutionBudget {
    pub max_loop_iterations: Option<u64>,
    pub max_reasoning_steps: Option<u64>,
    pub max_vm_instructions: Option<u64>,
    pub max_wall_time_ms: Option<u64>,
    pub max_allocated_bytes: Option<u64>,
}

impl ExecutionBudget {
    pub fn from_limits(limits: &serde_json::Map<String, serde_json::Value>) -> Self {
        let read = |name: &str| {
            limits
                .get(name)
                .and_then(serde_json::Value::as_u64)
                .filter(|value| *value > 0)
        };
        ExecutionBudget {
            max_loop_iterations: read("max_loop_iterations"),
            max_reasoning_steps: read("max_reasoning_steps"),
            max_vm_instructions: read("max_vm_instructions"),
            max_wall_time_ms: read("max_wall_time_ms"),
            max_allocated_bytes: read("max_allocated_bytes"),
        }
    }
}

/// `reasoning.event` processing mode (P0-5). `Off` records nothing and
/// returns step `0`; `Count` keeps per-type counters only (no event object
/// is ever built); `Full` additionally materializes the event into
/// `reasoning_trace` when a trace is enabled.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ReasoningEventMode {
    Off,
    Count,
    Full,
}

impl ReasoningEventMode {
    pub fn parse(name: &str) -> Option<Self> {
        match name {
            "off" => Some(ReasoningEventMode::Off),
            "count" => Some(ReasoningEventMode::Count),
            "full" => Some(ReasoningEventMode::Full),
            _ => None,
        }
    }

    pub fn name(self) -> &'static str {
        match self {
            ReasoningEventMode::Off => "off",
            ReasoningEventMode::Count => "count",
            ReasoningEventMode::Full => "full",
        }
    }
}

pub const EVENT_TYPES: [&str; 18] = [
    "REASON_STATE_CREATED",
    "RU_ACTIVATED",
    "CANDIDATE_GENERATED",
    "CANDIDATE_PRUNED",
    "HYPOTHESIS_CREATED",
    "HYPOTHESIS_VERIFIED",
    "HYPOTHESIS_REJECTED",
    "EVIDENCE_ADDED",
    "STATE_TRANSITION",
    "GOAL_UPDATED",
    "TERMINATION_INFERRED",
    // Lazy candidate space (spec v0.1 section 26). The runtime emits
    // CREATED / CONSTRAINT_ADDED / EXHAUSTED once per space or constraint;
    // per-candidate activity is counted, never recorded as events.
    "CANDIDATE_SPACE_CREATED",
    "CONSTRAINT_ADDED",
    "CANDIDATE_SKIPPED",
    "CANDIDATE_SPACE_EXHAUSTED",
    // Constraint Fusion (spec ReasonScript_Constraint_Fusion_v0_1 section 58).
    "CONSTRAINT_FUSED",
    "GENERATOR_REBUILT",
    "FUSION_FALLBACK",
];

/// P0-1 native runtime counters. Each one is incremented exactly where the
/// work happens; none is derived or estimated. The `*_ns` timers are only
/// accumulated under `--profile-runtime`.
#[derive(Default)]
pub struct Metrics {
    pub vm_instruction_count: Cell<u64>,
    pub reasoning_event_count: Cell<u64>,
    pub event_type_counts: RefCell<[u64; EVENT_TYPES.len()]>,
    pub candidate_pruned_count: Cell<u64>,
    pub relation_dispatch_count: Cell<u64>,
    pub relation_filter_count: Cell<u64>,
    pub relation_predicate_eval_count: Cell<u64>,
    pub relation_count_count: Cell<u64>,
    pub array_read_count: Cell<u64>,
    pub array_write_count: Cell<u64>,
    pub struct_field_read_count: Cell<u64>,
    pub struct_field_write_count: Cell<u64>,
    pub state_transition_count: Cell<u64>,
    pub branch_count: Cell<u64>,
    pub fast_path_count: Cell<u64>,
    /// Lazy candidate space counters (spec v0.1 section 47).
    pub candidate_space_estimated_size: Cell<u64>,
    pub candidate_generated_count: Cell<u64>,
    pub candidate_skipped_count: Cell<u64>,
    pub candidate_symbolically_excluded_count: Cell<u64>,
    /// Set once an exclusion count could not be derived exactly (any stored
    /// constraint); the metric then reports `null` (spec section 29).
    pub candidate_symbolic_exclusion_unknown: Cell<bool>,
    pub candidate_materialized_count: Cell<u64>,
    pub candidate_constraint_count: Cell<u64>,
    pub candidate_constraint_eval_count: Cell<u64>,
    pub candidate_space_next_count: Cell<u64>,
    /// Constraint Fusion v0.1 counters (cumulative across every
    /// CandidateSpace this VM touches) and "last observed space" snapshots
    /// (overwritten on every constraint addition -- see the v0.1 report's
    /// implementation-decisions section for why these are snapshots, not
    /// per-space cumulative sums, matching `fused_modulus` naturally being
    /// a property of whichever space was most recently constrained).
    pub constraint_fusion_count: Cell<u64>,
    pub constraint_fusion_rebuild_count: Cell<u64>,
    pub fusion_fallback_count: Cell<u64>,
    pub fused_modulus: Cell<i64>,
    pub fused_residue_count: Cell<u64>,
    pub fused_constraint_count: Cell<u64>,
    pub residual_constraint_count: Cell<u64>,
    pub predicate_execution_ns: Cell<u64>,
    pub relation_execution_ns: Cell<u64>,
    pub reasoning_event_ns: Cell<u64>,
    pub trace_execution_ns: Cell<u64>,
}

#[inline]
fn bump(cell: &Cell<u64>) {
    cell.set(cell.get() + 1);
}

/// `termination_reason` for the result envelope, derived from the error
/// code (`None` = the program completed).
pub fn termination_reason(code: Option<&str>) -> &'static str {
    match code {
        None => "completed",
        Some("RT-BUDGET-001") => "wall_time_budget",
        Some("RT-BUDGET-002") => "memory_budget",
        Some("RT-BUDGET-003") => "vm_instruction_budget",
        Some("RT-BUDGET-004") => "reasoning_step_budget",
        Some("RT-BUDGET-005") => "loop_iteration_budget",
        Some(_) => "runtime_error",
    }
}

pub struct Vm<'a> {
    functions: FastMap<&'a str, &'a Function>,
    budget: ExecutionBudget,
    max_call_depth: u32,
    tensors: RefCell<reasonscript_tensor_core::TensorStore>,
    reason_objects: RefCell<Env>,
    reasoning_bindings: Env,
    loop_trace: RefCell<Vec<serde_json::Value>>,
    loop_frames: RefCell<HashMap<String, Vec<(i64, serde_json::Value)>>>,
    trace_enabled: bool,
    trace_config: TraceConfig,
    trace_states: RefCell<Vec<Option<TraceState>>>,
    trace_bytes: Cell<usize>,
    trace_suppressed: Cell<bool>,
    trace_event_id: Cell<u64>,
    trace_frame_id: Cell<u64>,
    sampled_tail: RefCell<VecDeque<(serde_json::Value, usize)>>,
    event_mode: ReasoningEventMode,
    profile: bool,
    fast_path: bool,
    constraint_fusion: bool,
    metrics: Metrics,
    execution_ns: Cell<u64>,
    started: Cell<Option<Instant>>,
    alloc_start: Cell<crate::alloc_counter::Snapshot>,
    semantic_steps: Cell<u64>,
    loop_iterations: Cell<u64>,
    builder_appends: Cell<u64>,
    relation_rows_scanned: Cell<u64>,
    tensor_trace: RefCell<Vec<serde_json::Value>>,
    vision_trace: RefCell<Vec<serde_json::Value>>,
    reasoning_trace: RefCell<Vec<serde_json::Value>>,
    console_events: RefCell<Vec<crate::console_dispatch::ConsoleEvent>>,
    resource_root: PathBuf,
    filesystem_read: bool,
    filesystem_write: bool,
    backend: String,
    active_frames: RefCell<Vec<Rc<RefCell<Env>>>>,
    active_calculations: RefCell<Vec<Value>>,
    temporary_roots: RefCell<Vec<Value>>,
}

struct FrameGuard<'a, 'v> {
    vm: &'a Vm<'v>,
    traced: bool,
}

impl<'a, 'v> FrameGuard<'a, 'v> {
    fn new(vm: &'a Vm<'v>, env: &Rc<RefCell<Env>>, traceable: bool) -> Self {
        vm.active_frames.borrow_mut().push(env.clone());
        let traced = matches!(vm.trace_config.mode, TraceMode::Delta | TraceMode::Sampled)
            && !vm.trace_suppressed.get();
        if traced && traceable {
            let mut state = TraceState::new(&env.borrow());
            let id = vm.trace_frame_id.get() + 1;
            vm.trace_frame_id.set(id);
            state.frame_id = id;
            vm.trace_states.borrow_mut().push(Some(state));
        } else if traced {
            vm.trace_states.borrow_mut().push(None);
        }
        FrameGuard { vm, traced }
    }
}

impl<'a, 'v> Drop for FrameGuard<'a, 'v> {
    fn drop(&mut self) {
        self.vm.active_frames.borrow_mut().pop();
        if self.traced {
            self.vm.trace_states.borrow_mut().pop();
        }
    }
}

struct TempRootGuard<'a, 'v> {
    vm: &'a Vm<'v>,
    initial_len: usize,
}

impl<'a, 'v> TempRootGuard<'a, 'v> {
    fn new(vm: &'a Vm<'v>) -> Self {
        let initial_len = vm.temporary_roots.borrow().len();
        TempRootGuard { vm, initial_len }
    }
}

impl<'a, 'v> Drop for TempRootGuard<'a, 'v> {
    fn drop(&mut self) {
        self.vm
            .temporary_roots
            .borrow_mut()
            .truncate(self.initial_len);
    }
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
            DEFAULT_MAX_CALL_DEPTH,
            ExecutionBudget::default(),
        )
    }

    /// `max_call_depth` (Phase 4, "制御された再帰") and the P0-2
    /// `ExecutionBudget` both arrive through the
    /// `reasonscript-runtime-request/1.0` protocol's `context.limits`, the
    /// same mechanism the Tensor policy limits already use.
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
        max_call_depth: u32,
        budget: ExecutionBudget,
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
            budget,
            max_call_depth,
            tensors: RefCell::new(tensors),
            reason_objects: RefCell::new(Env::default()),
            reasoning_bindings: program
                .reasoning_bindings
                .iter()
                .map(|(name, value)| (name.clone(), Value::String(Rc::from(value.as_str()))))
                .collect(),
            loop_trace: RefCell::new(Vec::new()),
            loop_frames: RefCell::new(HashMap::new()),
            trace_enabled,
            trace_config: TraceConfig {
                mode: if trace_enabled {
                    TraceMode::Delta
                } else {
                    TraceMode::Off
                },
                ..TraceConfig::default()
            },
            trace_states: RefCell::new(Vec::new()),
            trace_bytes: Cell::new(0),
            trace_suppressed: Cell::new(false),
            trace_event_id: Cell::new(0),
            trace_frame_id: Cell::new(0),
            sampled_tail: RefCell::new(VecDeque::new()),
            event_mode: if trace_enabled {
                ReasoningEventMode::Full
            } else {
                ReasoningEventMode::Count
            },
            profile: false,
            fast_path: true,
            constraint_fusion: false,
            metrics: Metrics::default(),
            execution_ns: Cell::new(0),
            started: Cell::new(None),
            alloc_start: Cell::new(Default::default()),
            semantic_steps: Cell::new(0),
            loop_iterations: Cell::new(0),
            builder_appends: Cell::new(0),
            relation_rows_scanned: Cell::new(0),
            tensor_trace: RefCell::new(Vec::new()),
            vision_trace: RefCell::new(Vec::new()),
            reasoning_trace: RefCell::new(Vec::new()),
            console_events: RefCell::new(Vec::new()),
            resource_root,
            filesystem_read,
            filesystem_write,
            backend,
            active_frames: RefCell::new(Vec::new()),
            active_calculations: RefCell::new(Vec::new()),
            temporary_roots: RefCell::new(Vec::new()),
        }
    }

    pub fn loop_trace(&self) -> Vec<serde_json::Value> {
        let mut result = self.loop_trace.borrow().clone();
        if self.trace_config.mode == TraceMode::Sampled {
            result.extend(
                self.sampled_tail
                    .borrow()
                    .iter()
                    .map(|(event, _)| event.clone()),
            );
            result.sort_by_key(|event| event["event_id"].as_u64().unwrap_or(0));
            result.dedup_by_key(|event| event["event_id"].as_u64().unwrap_or(0));
        }
        result
    }

    pub fn configure_trace(&mut self, config: TraceConfig, event_mode: ReasoningEventMode) {
        self.trace_enabled = config.mode != TraceMode::Off;
        self.trace_config = config;
        self.event_mode = event_mode;
    }

    /// `--profile-runtime`: accumulate the per-section nanosecond timers.
    pub fn set_profile(&mut self, profile: bool) {
        self.profile = profile;
    }

    /// `context.fast_path = false` routes every primitive through the
    /// Generic Path (the Fast/Generic equivalence tests rely on this).
    pub fn set_fast_path(&mut self, fast_path: bool) {
        self.fast_path = fast_path;
    }

    /// `context.constraint_fusion = true` (default `false`, matching the
    /// pre-Fusion v0.1 behavior byte-for-byte): folds a prime
    /// `NotDivisibleBy(p)` `relation.filter`/`exclude_multiples_of`
    /// constraint into the CandidateSpace's generator instead of storing it
    /// as a residual constraint (Constraint Fusion v0.1, spec section 55).
    pub fn set_constraint_fusion(&mut self, constraint_fusion: bool) {
        self.constraint_fusion = constraint_fusion;
    }

    pub fn budget(&self) -> &ExecutionBudget {
        &self.budget
    }

    #[inline]
    fn delta_tracing(&self) -> bool {
        matches!(
            self.trace_config.mode,
            TraceMode::Delta | TraceMode::Sampled
        ) && !self.trace_suppressed.get()
    }

    #[inline]
    fn recording_events(&self) -> bool {
        self.event_mode == ReasoningEventMode::Full
            && self.trace_enabled
            && !self.trace_suppressed.get()
    }

    #[inline]
    fn profile_start(&self) -> Option<Instant> {
        if self.profile {
            Some(Instant::now())
        } else {
            None
        }
    }

    #[inline]
    fn profile_stop(&self, started: Option<Instant>, cell: &Cell<u64>) {
        if let Some(started) = started {
            cell.set(cell.get() + started.elapsed().as_nanos() as u64);
        }
    }

    /// One VM instruction (or terminator) about to execute. The counter and
    /// the instruction budget are checked every time; the wall-clock and
    /// memory budgets are sampled every 1024 instructions so
    /// `Instant::now()` stays off the hot path.
    #[inline]
    fn tick_instruction(&self) -> Result<(), RuntimeError> {
        let count = self.metrics.vm_instruction_count.get() + 1;
        self.metrics.vm_instruction_count.set(count);
        if count & 0x3ff == 0 {
            self.check_periodic_budget()?;
        }
        if let Some(max) = self.budget.max_vm_instructions {
            if count > max {
                return Err(RuntimeError::new(
                    "RT-BUDGET-003",
                    format!("VM instruction budget exceeded: {max}"),
                ));
            }
        }
        Ok(())
    }

    fn check_periodic_budget(&self) -> Result<(), RuntimeError> {
        if let (Some(max), Some(started)) = (self.budget.max_wall_time_ms, self.started.get()) {
            if started.elapsed().as_millis() as u64 > max {
                return Err(RuntimeError::new(
                    "RT-BUDGET-001",
                    format!("wall time budget exceeded: {max} ms"),
                ));
            }
        }
        if let Some(max) = self.budget.max_allocated_bytes {
            let live = crate::alloc_counter::live_bytes();
            if live > max {
                return Err(RuntimeError::new(
                    "RT-BUDGET-002",
                    format!("memory budget exceeded: {max} bytes (live: {live})"),
                ));
            }
        }
        Ok(())
    }

    pub fn trace_diagnostics(&self) -> Vec<serde_json::Value> {
        if self.trace_suppressed.get() {
            vec![
                serde_json::json!({"code": "TRACE-BUDGET-001", "severity": "warning", "category": "runtime.trace", "message": "trace size budget exceeded; further trace recording was disabled; execution continued"}),
            ]
        } else {
            Vec::new()
        }
    }

    pub fn runtime_metrics(&self) -> serde_json::Value {
        let m = &self.metrics;
        let counts = m.event_type_counts.borrow();
        let count_of = |name: &str| {
            EVENT_TYPES
                .iter()
                .position(|candidate| *candidate == name)
                .map_or(0, |index| counts[index])
        };
        let event_type_counts: serde_json::Map<String, serde_json::Value> = EVENT_TYPES
            .iter()
            .zip(counts.iter())
            .filter(|(_, count)| **count > 0)
            .map(|(name, count)| ((*name).to_owned(), serde_json::json!(count)))
            .collect();
        let alloc = crate::alloc_counter::snapshot();
        let start = self.alloc_start.get();
        let execution_ns = if self.execution_ns.get() > 0 {
            self.execution_ns.get()
        } else {
            self.started
                .get()
                .map_or(0, |started| started.elapsed().as_nanos() as u64)
        };
        let mut metrics = serde_json::json!({
            "loop_iterations": self.loop_iterations.get(),
            "semantic_reasoning_steps": self.semantic_steps.get(),
            "builder_appends": self.builder_appends.get(),
            "builder_full_copies": 0,
            "relation_rows_scanned": self.relation_rows_scanned.get(),
            "trace_bytes": self.trace_bytes.get(),
            "trace_mode": format!("{:?}", self.trace_config.mode).to_lowercase(),
            "vm_instruction_count": m.vm_instruction_count.get(),
            "reasoning_step_count": self.semantic_steps.get(),
            "reasoning_event_count": m.reasoning_event_count.get(),
            "reasoning_event_type_counts": event_type_counts,
            "hypothesis_test_count": count_of("HYPOTHESIS_VERIFIED") + count_of("HYPOTHESIS_REJECTED"),
            "candidate_pruned_count": m.candidate_pruned_count.get(),
            "relation_dispatch_count": m.relation_dispatch_count.get(),
            "relation_filter_count": m.relation_filter_count.get(),
            "relation_filter_rows_scanned": self.relation_rows_scanned.get(),
            "relation_predicate_eval_count": m.relation_predicate_eval_count.get(),
            "relation_count_count": m.relation_count_count.get(),
            "array_read_count": m.array_read_count.get(),
            "array_write_count": m.array_write_count.get(),
            "struct_field_read_count": m.struct_field_read_count.get(),
            "struct_field_write_count": m.struct_field_write_count.get(),
            "allocation_count": alloc.count.saturating_sub(start.count),
            "allocated_bytes": alloc.bytes.saturating_sub(start.bytes),
            "peak_live_bytes": alloc.peak,
            "state_transition_count": m.state_transition_count.get(),
            "branch_count": m.branch_count.get(),
            "loop_iteration_count": self.loop_iterations.get(),
            "fast_path_count": m.fast_path_count.get(),
            "fast_path_enabled": self.fast_path,
            "reasoning_event_mode": self.event_mode.name(),
            "runtime_execution_ns": execution_ns,
        });
        // Lazy candidate space counters (spec v0.1 sections 28, 47, 60).
        // `candidate_symbolically_excluded_count` is exact or `null`, never
        // an estimate (section 29); v0.1 holds no generic (VM callback)
        // predicates on candidate spaces, so every evaluation is symbolic.
        let excluded = if m.candidate_symbolic_exclusion_unknown.get() {
            serde_json::Value::Null
        } else {
            serde_json::json!(m.candidate_symbolically_excluded_count.get())
        };
        for (key, value) in [
            ("candidate_space_estimated_size", serde_json::json!(m.candidate_space_estimated_size.get())),
            ("candidate_generated_count", serde_json::json!(m.candidate_generated_count.get())),
            ("candidate_skipped_count", serde_json::json!(m.candidate_skipped_count.get())),
            ("candidate_symbolically_excluded_count", excluded),
            ("candidate_materialized_count", serde_json::json!(m.candidate_materialized_count.get())),
            ("candidate_constraint_count", serde_json::json!(m.candidate_constraint_count.get())),
            ("candidate_constraint_eval_count", serde_json::json!(m.candidate_constraint_eval_count.get())),
            ("candidate_space_next_count", serde_json::json!(m.candidate_space_next_count.get())),
            ("candidate_materialized_pruned_count", serde_json::json!(m.candidate_pruned_count.get())),
            ("candidate_generated_skipped_count", serde_json::json!(m.candidate_skipped_count.get())),
            ("symbolic_constraint_eval_count", serde_json::json!(m.candidate_constraint_eval_count.get())),
            ("generic_predicate_eval_count", serde_json::json!(0)),
            // Constraint Fusion v0.1 (spec section 30/59).
            ("constraint_fusion_count", serde_json::json!(m.constraint_fusion_count.get())),
            ("constraint_fusion_rebuild_count", serde_json::json!(m.constraint_fusion_rebuild_count.get())),
            ("fusion_fallback_count", serde_json::json!(m.fusion_fallback_count.get())),
            ("fused_modulus", serde_json::json!(m.fused_modulus.get())),
            ("fused_residue_count", serde_json::json!(m.fused_residue_count.get())),
            ("fused_constraint_count", serde_json::json!(m.fused_constraint_count.get())),
            ("residual_constraint_count", serde_json::json!(m.residual_constraint_count.get())),
        ] {
            metrics[key] = value;
        }
        if self.profile {
            metrics["predicate_execution_ns"] = serde_json::json!(m.predicate_execution_ns.get());
            metrics["relation_execution_ns"] = serde_json::json!(m.relation_execution_ns.get());
            metrics["reasoning_event_ns"] = serde_json::json!(m.reasoning_event_ns.get());
            metrics["trace_execution_ns"] = serde_json::json!(m.trace_execution_ns.get());
        }
        metrics
    }

    fn reserve_trace(&self, event: &serde_json::Value) -> Option<usize> {
        if !self.trace_enabled || self.trace_suppressed.get() {
            return None;
        }
        let bytes = serde_json::to_vec(event).ok()?.len();
        if bytes
            > self
                .trace_config
                .max_bytes
                .saturating_sub(self.trace_bytes.get())
        {
            self.trace_suppressed.set(true);
            return None;
        }
        self.trace_bytes.set(self.trace_bytes.get() + bytes);
        Some(bytes)
    }

    fn trace_assign(&self, name: &str, old: Option<&Value>, value: &Value) {
        if self.trace_suppressed.get() {
            return;
        }
        if let Some(state) = self
            .trace_states
            .borrow_mut()
            .last_mut()
            .and_then(Option::as_mut)
        {
            state.assign(name, old, value);
        }
    }

    fn trace_mutation(&self, owner: &Value, suffix: &[String], old: Option<&Value>, value: &Value) {
        if self.trace_suppressed.get() {
            return;
        }
        for state in self.trace_states.borrow_mut().iter_mut().flatten() {
            state.mutation(owner, suffix, old, value);
        }
    }

    /// `materialize` builds the event payload and is only invoked in
    /// `Full` mode with an enabled trace (P0-5 lazy materialization); in
    /// `Count` mode a `reasoning.event` call costs two counter increments.
    fn semantic_event<F>(&self, event_type: &str, materialize: F) -> Result<Value, RuntimeError>
    where
        F: FnOnce() -> (
            serde_json::Value,
            serde_json::Value,
            serde_json::Value,
            serde_json::Value,
        ),
    {
        let Some(type_index) = EVENT_TYPES.iter().position(|name| *name == event_type) else {
            return Err(RuntimeError::new(
                "REASON-EVENT-001",
                format!("invalid reasoning event: {event_type}"),
            ));
        };
        if self.event_mode == ReasoningEventMode::Off {
            return Ok(Value::Int(0));
        }
        let timer = self.profile_start();
        bump(&self.metrics.reasoning_event_count);
        self.metrics.event_type_counts.borrow_mut()[type_index] += 1;
        let step = self.semantic_steps.get() + 1;
        self.semantic_steps.set(step);
        if let Some(max) = self.budget.max_reasoning_steps {
            if step > max {
                return Err(RuntimeError::new(
                    "RT-BUDGET-004",
                    format!("reasoning step budget exceeded: {max}"),
                ));
            }
        }
        if self.recording_events() {
            let (subject, evidence, affected, metadata) = materialize();
            let event = serde_json::json!({
                "event_id": format!("reason-event-{step}"),
                "reasoning_step_id": step,
                "event_type": event_type,
                "source_ru": null,
                "state_revision": step,
                "subject": subject,
                "evidence": evidence,
                "affected_entities": affected,
                "metadata": metadata,
            });
            if self.reserve_trace(&event).is_some() {
                self.reasoning_trace.borrow_mut().push(event);
            }
        }
        self.profile_stop(timer, &self.metrics.reasoning_event_ns);
        Ok(Value::Int(step as i64))
    }

    /// `candidate_space.*` dispatch (spec v0.1 sections 7-15 and 21).
    /// Arguments are evaluated in place: no argument vector and no per-call
    /// allocation besides a new space handle.
    fn call_candidate_space(
        &self,
        function_id: &str,
        arguments: &[Expr],
        env: &Rc<RefCell<Env>>,
        call_depth: u32,
    ) -> Result<Value, RuntimeError> {
        let name = function_id
            .strip_prefix("candidate_space.")
            .unwrap_or(function_id);
        let int = |value: Value, what: &str| match value {
            Value::Int(value) => Ok(value),
            other => Err(RuntimeError::new(
                "CS-002",
                format!(
                    "candidate_space.{name} {what} must be Int, got {}",
                    other.type_name()
                ),
            )),
        };
        let space = |value: Value| match value {
            Value::CandidateSpace(space) => Ok(space),
            other => Err(RuntimeError::new(
                "CS-002",
                format!(
                    "candidate_space.{name} requires a CandidateSpace, got {}",
                    other.type_name()
                ),
            )),
        };
        match (name, arguments) {
            ("isqrt", [n]) => {
                let n = int(self.eval_expr(n, env, call_depth)?, "argument")?;
                if n < 0 {
                    return Err(RuntimeError::new(
                        "CS-005",
                        format!("candidate_space.isqrt requires a non-negative Int, got {n}"),
                    ));
                }
                Ok(Value::Int(isqrt(n)))
            }
            ("range" | "wheel6", [lower, upper]) => {
                let lower = int(self.eval_expr(lower, env, call_depth)?, "lower bound")?;
                let upper = int(self.eval_expr(upper, env, call_depth)?, "upper bound")?;
                let generator = if name == "range" {
                    Generator::Range
                } else {
                    Generator::Wheel6
                };
                let created = CandidateSpace::new(generator, lower, upper);
                let estimated = created.estimated_size();
                let m = &self.metrics;
                m.candidate_space_estimated_size
                    .set(m.candidate_space_estimated_size.get() + estimated);
                let value = Value::CandidateSpace(Rc::new(RefCell::new(created)));
                self.semantic_event("CANDIDATE_SPACE_CREATED", || {
                    (
                        serde_json::json!("candidate_space"),
                        to_json(&value),
                        serde_json::json!([]),
                        serde_json::json!({ "estimated_size": estimated }),
                    )
                })?;
                Ok(value)
            }
            ("next", [source]) => {
                let space = space(self.eval_expr(source, env, call_depth)?)?;
                bump(&self.metrics.candidate_space_next_count);
                match self.candidate_peek(&space)? {
                    Some(candidate) => {
                        space.borrow_mut().peeked = None;
                        bump(&self.metrics.candidate_generated_count);
                        Ok(Value::Int(candidate))
                    }
                    None => {
                        self.candidate_report_exhausted(&space)?;
                        Err(RuntimeError::new(
                            "CS-003",
                            "candidate space is exhausted; check candidate_space.is_exhausted before next",
                        ))
                    }
                }
            }
            ("is_exhausted", [source]) => {
                let space = space(self.eval_expr(source, env, call_depth)?)?;
                let exhausted = self.candidate_peek(&space)?.is_none();
                if exhausted {
                    self.candidate_report_exhausted(&space)?;
                }
                Ok(Value::Bool(exhausted))
            }
            ("exclude_multiples_of", [source, modulus]) => {
                let space = space(self.eval_expr(source, env, call_depth)?)?;
                let m = int(self.eval_expr(modulus, env, call_depth)?, "modulus")?;
                if m == 0 {
                    return Err(RuntimeError::new(
                        "CS-004",
                        "candidate_space.exclude_multiples_of modulus must be non-zero",
                    ));
                }
                self.candidate_with_constraint(
                    &space,
                    Constraint::Modulo {
                        m,
                        op: CmpOp::Ne,
                        r: 0,
                    },
                )
            }
            ("reset", [source]) => {
                let space = space(self.eval_expr(source, env, call_depth)?)?;
                let mut reset = space.borrow().clone();
                reset.reset_cursor();
                Ok(Value::CandidateSpace(Rc::new(RefCell::new(reset))))
            }
            ("materialize", [source]) => {
                let space = space(self.eval_expr(source, env, call_depth)?)?;
                self.candidate_materialize(&space)
            }
            _ => Err(RuntimeError::new(
                "CS-001",
                format!("unknown candidate_space function or argument count: {function_id}"),
            )),
        }
    }

    /// Generates up to the next accepted candidate and parks it in
    /// `peeked` (the `is_exhausted` lookahead). Every generator value is
    /// checked against the constraints exactly once; rejected values are
    /// counted as skipped. The wall-time/memory budget is sampled every
    /// 1024 skipped values, like `tick_instruction` does for instructions.
    fn candidate_peek(
        &self,
        space: &Rc<RefCell<CandidateSpace>>,
    ) -> Result<Option<i64>, RuntimeError> {
        let mut space = space.borrow_mut();
        if space.peeked.is_some() {
            return Ok(space.peeked);
        }
        let mut evals = 0u64;
        let mut skipped = 0u64;
        let found = loop {
            let Some(candidate) = space.generate_next() else {
                break None;
            };
            if space.accepts(candidate, &mut evals) {
                break Some(candidate);
            }
            skipped += 1;
            if skipped & 0x3ff == 0 {
                self.check_periodic_budget()?;
            }
        };
        let m = &self.metrics;
        m.candidate_constraint_eval_count
            .set(m.candidate_constraint_eval_count.get() + evals);
        m.candidate_skipped_count
            .set(m.candidate_skipped_count.get() + skipped);
        space.peeked = found;
        Ok(found)
    }

    fn candidate_report_exhausted(
        &self,
        space: &Rc<RefCell<CandidateSpace>>,
    ) -> Result<(), RuntimeError> {
        if space.borrow().exhausted_reported {
            return Ok(());
        }
        space.borrow_mut().exhausted_reported = true;
        self.semantic_event("CANDIDATE_SPACE_EXHAUSTED", || {
            (
                serde_json::json!("candidate_space"),
                space.borrow().to_json(),
                serde_json::json!([]),
                serde_json::json!({}),
            )
        })?;
        Ok(())
    }

    /// `relation.filter` / `exclude_multiples_of` over a candidate space
    /// (spec sections 18-19): a new handle with the constraint added. No
    /// candidate is visited; the cursor never moves backwards.
    fn candidate_with_constraint(
        &self,
        space: &Rc<RefCell<CandidateSpace>>,
        constraint: Constraint,
    ) -> Result<Value, RuntimeError> {
        let mut next = space.borrow().clone();
        next.unpeek();
        let description = constraint.to_string();
        let mut added = 0u64;
        let mut non_fused_added = 0u64;
        let mut excluded = 0u64;
        let mut fused_this_call = false;
        let mut fallback_this_call = false;
        for leaf in constraint.conjuncts() {
            // `unvisited_count` (O(residue count)) is computed by `add`
            // itself, only for a leaf that actually folds or fuses -- never
            // unconditionally here. Computing it up front for every leaf
            // regardless of outcome was a real regression once the fused
            // residue count grew large (a `relation.filter` call that only
            // fell back to a residual constraint still paid the full O(R)
            // cost); see `FusedConstraintSet::residues`'s doc comment.
            match next.add(leaf, self.constraint_fusion) {
                Added::Folded { excluded: count } => {
                    added += 1;
                    non_fused_added += 1;
                    if next.residual_constraints.is_empty() {
                        excluded += count;
                    } else {
                        self.metrics.candidate_symbolic_exclusion_unknown.set(true);
                    }
                }
                Added::Fused { excluded: count, .. } => {
                    added += 1;
                    fused_this_call = true;
                    // Exact, like a bound fold: `unvisited_count` already
                    // reflects the narrowed generator (spec section 29).
                    if next.residual_constraints.is_empty() {
                        excluded += count;
                    } else {
                        self.metrics.candidate_symbolic_exclusion_unknown.set(true);
                    }
                }
                Added::Stored { fusion_fallback } => {
                    added += 1;
                    non_fused_added += 1;
                    fallback_this_call |= fusion_fallback;
                    self.metrics.candidate_symbolic_exclusion_unknown.set(true);
                }
                Added::Duplicate => {}
            }
        }
        let m = &self.metrics;
        m.candidate_constraint_count
            .set(m.candidate_constraint_count.get() + added);
        m.candidate_symbolically_excluded_count
            .set(m.candidate_symbolically_excluded_count.get() + excluded);
        m.fused_modulus.set(next.fused.modulus);
        m.fused_residue_count.set(next.fused.residues.len() as u64);
        m.fused_constraint_count.set(next.fused_primes.len() as u64);
        m.residual_constraint_count
            .set(next.residual_constraints.len() as u64);
        let constraint_count = next.residual_constraints.len();
        let final_modulus = next.fused.modulus;
        let final_residue_count = next.fused.residues.len();
        let value = Value::CandidateSpace(Rc::new(RefCell::new(next)));
        if fused_this_call {
            m.constraint_fusion_count.set(m.constraint_fusion_count.get() + 1);
            m.constraint_fusion_rebuild_count
                .set(m.constraint_fusion_rebuild_count.get() + 1);
            self.semantic_event("CONSTRAINT_FUSED", || {
                (
                    serde_json::json!("candidate_space"),
                    serde_json::json!(description),
                    serde_json::json!([]),
                    serde_json::json!({ "fused_modulus": final_modulus, "fused_residue_count": final_residue_count }),
                )
            })?;
            self.semantic_event("GENERATOR_REBUILT", || {
                (
                    serde_json::json!("candidate_space"),
                    serde_json::json!(format!("mod {final_modulus}")),
                    serde_json::json!([]),
                    serde_json::json!({ "fused_residue_count": final_residue_count }),
                )
            })?;
        }
        if fallback_this_call {
            m.fusion_fallback_count.set(m.fusion_fallback_count.get() + 1);
            self.semantic_event("FUSION_FALLBACK", || {
                (
                    serde_json::json!("candidate_space"),
                    serde_json::json!(description),
                    serde_json::json!([]),
                    serde_json::json!({}),
                )
            })?;
        }
        // Preserves the pre-Fusion v0.1 behavior exactly when nothing in
        // this call was fused (CONSTRAINT_ADDED always fired, even for an
        // all-duplicate call); only a call that fused every leaf skips it.
        if !fused_this_call || non_fused_added > 0 {
            self.semantic_event("CONSTRAINT_ADDED", || {
                (
                    serde_json::json!("candidate_space"),
                    serde_json::json!(description),
                    serde_json::json!([]),
                    serde_json::json!({
                        "added": non_fused_added,
                        "constraint_count": constraint_count,
                        "symbolically_excluded": excluded,
                    }),
                )
            })?;
        }
        Ok(value)
    }

    /// Explicit materialization (debug, export, compatibility): every
    /// accepted value of the domain, independent of the cursor.
    fn candidate_materialize(
        &self,
        space: &Rc<RefCell<CandidateSpace>>,
    ) -> Result<Value, RuntimeError> {
        let mut probe = space.borrow().clone();
        probe.reset_cursor();
        let mut evals = 0u64;
        let mut visited = 0u64;
        let mut items = Vec::new();
        while let Some(candidate) = probe.generate_next() {
            visited += 1;
            if visited & 0x3ff == 0 {
                self.check_periodic_budget()?;
            }
            if probe.accepts(candidate, &mut evals) {
                items.push(Value::Int(candidate));
            }
        }
        let m = &self.metrics;
        m.candidate_constraint_eval_count
            .set(m.candidate_constraint_eval_count.get() + evals);
        m.candidate_materialized_count
            .set(m.candidate_materialized_count.get() + items.len() as u64);
        Ok(Value::Array(Rc::new(RefCell::new(items))))
    }

    fn retain_state_event(&self, event: serde_json::Value) {
        if self.trace_config.mode == TraceMode::Sampled {
            let id = event["event_id"].as_u64().unwrap_or(0);
            let selected = id <= 100 || id % 100 == 0;
            let mut tail = self.sampled_tail.borrow_mut();
            if tail.len() == 100 {
                if let Some((_, size)) = tail.pop_front() {
                    self.trace_bytes
                        .set(self.trace_bytes.get().saturating_sub(size));
                }
            }
            if let Some(size) = self.reserve_trace(&event) {
                if selected {
                    tail.push_back((event.clone(), 0));
                    self.loop_trace.borrow_mut().push(event);
                } else {
                    tail.push_back((event, size));
                }
            }
        } else if self.reserve_trace(&event).is_some() {
            self.loop_trace.borrow_mut().push(event);
        }
    }

    fn finish_trace(&self) -> Result<(), RuntimeError> {
        if self.trace_suppressed.get() {
            return Ok(());
        }
        let timer = self.profile_start();
        let mut states = self.trace_states.borrow_mut();
        if let Some(state) = states.last_mut().and_then(Option::as_mut) {
            if let Some(mut event) = state.finish() {
                let id = self.trace_event_id.get() + 1;
                self.trace_event_id.set(id);
                event["event_id"] = serde_json::json!(id);
                event["step_id"] = serde_json::json!(id);
                state.previous_event_id = Some(id);
                if self.trace_config.checkpoint_interval > 0
                    && id % self.trace_config.checkpoint_interval == 0
                {
                    event["checkpoint"] = state.checkpoint();
                }
                drop(states);
                self.retain_state_event(event);
            }
        }
        self.profile_stop(timer, &self.metrics.trace_execution_ns);
        Ok(())
    }

    pub fn tensor_trace(&self) -> Vec<serde_json::Value> {
        self.tensor_trace.borrow().clone()
    }

    pub fn tensor_metadata(&self) -> Vec<serde_json::Value> {
        self.tensors.borrow().metadata()
    }

    /// Serialize a calculation result for an explicit process boundary.
    /// Normal host results retain lightweight tensor handles; cluster workers
    /// opt into this representation so a coordinator can consume the actual
    /// Tensor value after the worker process exits.
    pub fn transport_value(&self, value: &Value) -> serde_json::Value {
        match value {
            Value::Tensor(id) => self.tensors.borrow().get(id).map_or_else(
                |_| serde_json::json!({"tensor_id": id.as_ref()}),
                |tensor| {
                    serde_json::json!({
                        "tensor_id": id.as_ref(),
                        "shape": tensor.shape,
                        "dtype": tensor.dtype.name(),
                        "data": tensor.data,
                    })
                },
            ),
            Value::Array(items) => serde_json::Value::Array(
                items
                    .borrow()
                    .iter()
                    .map(|item| self.transport_value(item))
                    .collect(),
            ),
            Value::Struct(value) => {
                let fields = value
                    .fields
                    .borrow()
                    .iter()
                    .map(|(name, item)| (name.clone(), self.transport_value(item)))
                    .collect::<serde_json::Map<_, _>>();
                serde_json::json!({"type": value.type_name, "fields": fields})
            }
            _ => to_json(value),
        }
    }

    pub fn vision_trace(&self) -> Vec<serde_json::Value> {
        self.vision_trace.borrow().clone()
    }

    pub fn reasoning_trace(&self) -> Vec<serde_json::Value> {
        self.reasoning_trace.borrow().clone()
    }

    pub fn console_events(&self) -> Vec<crate::console_dispatch::ConsoleEvent> {
        self.console_events.borrow().clone()
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
        let started = Instant::now();
        self.started.set(Some(started));
        self.alloc_start.set(crate::alloc_counter::snapshot());
        let result = self.run_calculations_inner(program);
        self.execution_ns
            .set(started.elapsed().as_nanos().max(1) as u64);
        result
    }

    fn run_calculations_inner(
        &self,
        program: &Program,
    ) -> Result<Vec<(String, Value)>, RuntimeError> {
        let mut object_bindings = Env::default();
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
        self.active_calculations.borrow_mut().clear();
        for calculation_id in &program.calculations {
            let function = *self.functions.get(calculation_id.as_str()).ok_or_else(|| {
                RuntimeError::new(
                    "RT-CALL-001",
                    format!("unknown calculation: {calculation_id}"),
                )
            })?;
            let mut env_map: Env = calculations
                .iter()
                .map(|(name, value)| (name.clone(), value.clone()))
                .collect();
            env_map.extend(self.reasoning_bindings.clone());
            env_map.extend(
                self.reason_objects
                    .borrow()
                    .iter()
                    .map(|(name, value)| (name.clone(), value.clone())),
            );
            let env = Rc::new(RefCell::new(env_map));
            match self.run_function(function, &env, 0)? {
                Outcome::Result(value) => {
                    self.active_calculations.borrow_mut().push(value.clone());
                    calculations.push((calculation_id.clone(), value));
                }
                Outcome::NoValue => {}
                Outcome::Return(_) => {
                    return Err(RuntimeError::new(
                        "IR-EXEC-005",
                        format!("calculation {calculation_id} used return instead of result"),
                    ))
                }
            }
            // A calculation boundary is not a tensor ownership boundary:
            // optimizer/autograd state can still retain handles referenced by
            // subsequent calculations.  The VM owns one fresh TensorStore per
            // program run, so defer collection until that store is dropped.
        }
        Ok(calculations)
    }

    fn push_temporary_root(&self, value: Value) {
        // Roots exist only for the tensor collector; with no live tensors no
        // value can reference one, so skip the clone-and-push (P0-6).
        if self.tensors.borrow().is_empty() {
            return;
        }
        self.temporary_roots.borrow_mut().push(value);
    }

    fn run_function(
        &self,
        function: &Function,
        env: &Rc<RefCell<Env>>,
        call_depth: u32,
    ) -> Result<Outcome, RuntimeError> {
        let traceable = function.blocks.iter().any(|block| {
            block
                .instructions
                .iter()
                .any(|instruction| matches!(instruction, Instruction::TraceLoopStart { .. }))
        });
        let _frame_guard = FrameGuard::new(self, env, traceable);
        let blocks: FastMap<&str, &Block> = function
            .blocks
            .iter()
            .map(|block| (block.id.as_str(), block))
            .collect();
        let mut current = function.entry_block.as_str();
        // P0-2: the per-block visit counter (the fixed 10,000 cap) is gone.
        // Loop iterations are budgeted at `TraceLoopStart`; the wall-time,
        // memory and instruction budgets in `tick_instruction` cover the rest.
        loop {
            let block = blocks.get(current).ok_or_else(|| {
                RuntimeError::new("IR-EXEC-006", format!("unknown block: {current}"))
            })?;
            for instruction in &block.instructions {
                self.tick_instruction()?;
                self.execute_instruction(instruction, env, call_depth)?;
                self.collect_tensors();
            }
            self.tick_instruction()?;
            match &block.terminator {
                Terminator::Jump { target } => {
                    current = self.resolve_block_id(&blocks, target)?;
                }
                Terminator::Branch {
                    condition,
                    then,
                    else_target,
                } => {
                    bump(&self.metrics.branch_count);
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
                    let value = self.eval_expr(value, env, call_depth)?;
                    self.finish_trace()?;
                    return Ok(Outcome::Result(value));
                }
                Terminator::Return { value } => {
                    let value = self.eval_expr(value, env, call_depth)?;
                    self.finish_trace()?;
                    return Ok(Outcome::Return(value));
                }
                Terminator::Trap { code, message } => {
                    if code == "IR-NO-VALUE" {
                        return Ok(Outcome::NoValue);
                    }
                    return Err(RuntimeError::new(code, message.clone()));
                }
                Terminator::Match { subject, arms } => {
                    bump(&self.metrics.branch_count);
                    let subject_value = self.eval_expr(subject, env, call_depth)?;
                    let mut matched_target: Option<&str> = None;
                    for arm in arms {
                        let Some(bindings) = match_pattern(&arm.pattern, &subject_value) else {
                            continue;
                        };
                        let previous: Vec<(String, Option<Value>)> = {
                            let mut env_mut = env.borrow_mut();
                            bindings
                                .into_iter()
                                .map(|(name, value)| {
                                    let old = env_mut.insert(name.clone(), value);
                                    (name, old)
                                })
                                .collect()
                        };
                        let guard_ok = match &arm.guard {
                            None => true,
                            Some(guard_expr) => {
                                match self.eval_expr(guard_expr, env, call_depth)? {
                                    Value::Bool(value) => value,
                                    other => {
                                        return Err(RuntimeError::new(
                                            "IR-EXEC-007",
                                            format!(
                                                "match guard must be Bool, got {}",
                                                other.type_name()
                                            ),
                                        ))
                                    }
                                }
                            }
                        };
                        if guard_ok {
                            for (name, old) in &previous {
                                if let Some(value) = env.borrow().get(name) {
                                    self.trace_assign(name, old.as_ref(), value);
                                }
                            }
                            matched_target = Some(arm.target.as_str());
                            break;
                        }
                        let mut env_mut = env.borrow_mut();
                        for (name, old_value) in previous {
                            match old_value {
                                Some(value) => {
                                    env_mut.insert(name, value);
                                }
                                None => {
                                    env_mut.remove(&name);
                                }
                            }
                        }
                    }
                    let Some(target) = matched_target else {
                        return Err(RuntimeError::new(
                            "RT-MATCH-001",
                            "no match arm satisfied the value",
                        ));
                    };
                    current = self.resolve_block_id(&blocks, target)?;
                }
            }
        }
    }

    fn collect_tensors(&self) {
        // ponytail: tensor programs still walk every root per instruction;
        // collect only after tensor-creating ops if that profiles hot.
        if self.tensors.borrow().is_empty() {
            return;
        }
        let mut roots = std::collections::HashSet::new();
        let mut visited_arrays = std::collections::HashSet::new();
        let mut visited_structs = std::collections::HashSet::new();

        // 1. All bindings in all active frames (including suspended callers)
        for frame in self.active_frames.borrow().iter() {
            let env = frame.borrow();
            for value in env.values() {
                collect_tensor_ids(value, &mut roots, &mut visited_arrays, &mut visited_structs);
            }
        }

        // 2. Retained prior calculation results
        for value in self.active_calculations.borrow().iter() {
            collect_tensor_ids(value, &mut roots, &mut visited_arrays, &mut visited_structs);
        }

        // 3. Temporary roots (in-progress arguments, return handoffs, intermediates)
        for value in self.temporary_roots.borrow().iter() {
            collect_tensor_ids(value, &mut roots, &mut visited_arrays, &mut visited_structs);
        }

        // 4. Bound reason objects and reasoning bindings
        for value in self.reason_objects.borrow().values() {
            collect_tensor_ids(value, &mut roots, &mut visited_arrays, &mut visited_structs);
        }
        for value in self.reasoning_bindings.values() {
            collect_tensor_ids(value, &mut roots, &mut visited_arrays, &mut visited_structs);
        }

        self.tensors.borrow_mut().collect(&roots);
    }

    fn resolve_block_id<'b>(
        &self,
        blocks: &FastMap<&'b str, &'b Block>,
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
        env: &Rc<RefCell<Env>>,
        call_depth: u32,
    ) -> Result<(), RuntimeError> {
        match instruction {
            Instruction::TraceLoopStart { loop_id, counter } => {
                let iteration = {
                    let mut env_mut = env.borrow_mut();
                    match env_mut.get_mut(counter) {
                        Some(Value::Int(value)) => {
                            *value += 1;
                            *value
                        }
                        _ => {
                            return Err(RuntimeError::new(
                                "IR-EXEC-009",
                                "loop trace counter is missing",
                            ))
                        }
                    }
                };
                let iterations = self.loop_iterations.get() + 1;
                self.loop_iterations.set(iterations);
                if let Some(max) = self.budget.max_loop_iterations {
                    if iterations > max {
                        return Err(RuntimeError::new(
                            "RT-BUDGET-005",
                            format!("loop iteration budget exceeded: {max}"),
                        ));
                    }
                }
                if !self.trace_suppressed.get() {
                    match self.trace_config.mode {
                        TraceMode::Off => {}
                        TraceMode::Full => {
                            let key = format!("{}:{loop_id}", self.active_frames.borrow().len());
                            self.loop_frames
                                .borrow_mut()
                                .entry(key)
                                .or_default()
                                .push((iteration, trace_env(&env.borrow())));
                        }
                        _ => {
                            if let Some(state) = self
                                .trace_states
                                .borrow_mut()
                                .last_mut()
                                .and_then(Option::as_mut)
                            {
                                state.begin(loop_id, iteration);
                            }
                        }
                    }
                }
                Ok(())
            }
            Instruction::TraceLoopEnd {
                loop_id,
                break_triggered,
                continue_triggered,
            } => {
                if self.trace_config.mode == TraceMode::Off || self.trace_suppressed.get() {
                    return Ok(());
                }
                let timer = self.profile_start();
                if self.trace_config.mode == TraceMode::Full {
                    let key = format!("{}:{loop_id}", self.active_frames.borrow().len());
                    let (iteration, previous_state) = self
                        .loop_frames
                        .borrow_mut()
                        .get_mut(&key)
                        .and_then(Vec::pop)
                        .ok_or_else(|| {
                            RuntimeError::new("IR-EXEC-009", "loop trace frame is missing")
                        })?;
                    let event = serde_json::json!({
                        "loop_id": loop_id, "iteration": iteration, "condition": true,
                        "previous_state": previous_state, "updated_state": trace_env(&env.borrow()),
                        "break_triggered": break_triggered, "continue_triggered": continue_triggered,
                    });
                    if self.reserve_trace(&event).is_some() {
                        self.loop_trace.borrow_mut().push(event);
                    }
                } else {
                    let id = self.trace_event_id.get() + 1;
                    self.trace_event_id.set(id);
                    let mut states = self.trace_states.borrow_mut();
                    let state = states.last_mut().and_then(Option::as_mut).ok_or_else(|| {
                        RuntimeError::new("TRACE-DELTA-001", "trace state is missing")
                    })?;
                    let first = state.previous_event_id.is_none();
                    let mut event = state.end(loop_id)?;
                    event["event_id"] = serde_json::json!(id);
                    state.previous_event_id = Some(id);
                    event["step_id"] = serde_json::json!(id);
                    event["break_triggered"] = serde_json::json!(break_triggered);
                    event["continue_triggered"] = serde_json::json!(continue_triggered);
                    if first
                        || (self.trace_config.checkpoint_interval > 0
                            && id % self.trace_config.checkpoint_interval == 0)
                    {
                        event["checkpoint"] = state.checkpoint();
                    }
                    drop(states);
                    self.retain_state_event(event);
                }
                self.profile_stop(timer, &self.metrics.trace_execution_ns);
                Ok(())
            }
            Instruction::Assign { target, expr } => {
                let value = self.eval_expr(expr, env, call_depth)?;
                bump(&self.metrics.state_transition_count);
                if self.delta_tracing() {
                    self.trace_assign(target, env.borrow().get(target), &value);
                }
                // Overwrite in place: `insert(target.clone(), ..)` allocated a
                // fresh key String on every assignment (P0-6).
                let mut env_mut = env.borrow_mut();
                match env_mut.get_mut(target) {
                    Some(slot) => *slot = value,
                    None => {
                        env_mut.insert(target.clone(), value);
                    }
                }
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
                let _guard = TempRootGuard::new(self);
                let collection_value = self.eval_expr(collection, env, call_depth)?;
                self.push_temporary_root(collection_value.clone());
                let index_value = self.eval_expr(index, env, call_depth)?;
                self.push_temporary_root(index_value.clone());
                let new_value = self.eval_expr(expr, env, call_depth)?;
                match &collection_value {
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
                        if index_int < 0 || index_int as usize >= items.borrow().len() {
                            return Err(RuntimeError::new(
                                "RT-INDEX-002",
                                format!("index out of range: {index_int}"),
                            ));
                        }
                        self.trace_mutation(
                            &collection_value,
                            &[index_int.to_string()],
                            Some(&items.borrow()[index_int as usize]),
                            &new_value,
                        );
                        items.borrow_mut()[index_int as usize] = new_value;
                        bump(&self.metrics.array_write_count);
                        bump(&self.metrics.state_transition_count);
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
                let _guard = TempRootGuard::new(self);
                let owner = self.eval_expr(object, env, call_depth)?;
                self.push_temporary_root(owner.clone());
                let new_value = self.eval_expr(expr, env, call_depth)?;
                match &owner {
                    Value::Struct(struct_value) => {
                        if !struct_value.fields.borrow().contains_key(member) {
                            return Err(RuntimeError::new(
                                "RT-FIELD-002",
                                "invalid field assignment target",
                            ));
                        }
                        self.trace_mutation(
                            &owner,
                            &["fields".to_owned(), member.clone()],
                            struct_value.fields.borrow().get(member),
                            &new_value,
                        );
                        struct_value
                            .fields
                            .borrow_mut()
                            .insert(member.clone(), new_value);
                        bump(&self.metrics.struct_field_write_count);
                        bump(&self.metrics.state_transition_count);
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
        env: &Rc<RefCell<Env>>,
        call_depth: u32,
    ) -> Result<Value, RuntimeError> {
        self.eval_expr_inner(expr, env, call_depth)
            .map_err(|error| error.with_source_location(expr.source_span()))
    }

    fn eval_expr_inner(
        &self,
        expr: &Expr,
        env: &Rc<RefCell<Env>>,
        call_depth: u32,
    ) -> Result<Value, RuntimeError> {
        match expr {
            Expr::Const {
                kind,
                value,
                cached,
                ..
            } => {
                if let Some(cached) = cached.get() {
                    return Ok(cached.clone());
                }
                let decoded = const_value(kind, value)?;
                let _ = cached.set(decoded.clone());
                Ok(decoded)
            }
            Expr::Local { name, .. } => env.borrow().get(name).cloned().ok_or_else(|| {
                RuntimeError::new("RT-NAME-001", format!("unknown runtime name: {name}"))
            }),
            Expr::Array { elements, .. } => {
                let _guard = TempRootGuard::new(self);
                let mut items = Vec::with_capacity(elements.len());
                for element in elements {
                    let val = self.eval_expr(element, env, call_depth)?;
                    self.push_temporary_root(val.clone());
                    items.push(val);
                }
                Ok(Value::Array(Rc::new(RefCell::new(items))))
            }
            Expr::Struct {
                type_name, fields, ..
            } => {
                let _guard = TempRootGuard::new(self);
                let mut evaluated = Env::with_capacity_and_hasher(fields.len(), Default::default());
                for (name, field_expr) in fields {
                    let val = self.eval_expr(field_expr, env, call_depth)?;
                    self.push_temporary_root(val.clone());
                    evaluated.insert(name.clone(), val);
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
                let _guard = TempRootGuard::new(self);
                let left_value = self.eval_expr(left, env, call_depth)?;
                self.push_temporary_root(left_value.clone());
                let right_value = self.eval_expr(right, env, call_depth)?;
                eval_binary(operator, left_value, right_value)
            }
            Expr::Comparison {
                operator,
                left,
                right,
                ..
            } => {
                let _guard = TempRootGuard::new(self);
                let left_value = self.eval_expr(left, env, call_depth)?;
                self.push_temporary_root(left_value.clone());
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
                let _guard = TempRootGuard::new(self);
                let collection_value = self.eval_expr(collection, env, call_depth)?;
                self.push_temporary_root(collection_value.clone());
                let index_value = self.eval_expr(index, env, call_depth)?;
                bump(&self.metrics.array_read_count);
                index_value_lookup(collection_value, index_value)
            }
            Expr::Member { object, member, .. } => {
                let owner = self.eval_expr(object, env, call_depth)?;
                match &owner {
                    Value::Struct(_) => bump(&self.metrics.struct_field_read_count),
                    Value::Array(_) => bump(&self.metrics.array_read_count),
                    _ => {}
                }
                member_lookup(owner, member)
            }
            Expr::CallTensor {
                function_id,
                arguments,
                source_span,
            } => {
                let _guard = TempRootGuard::new(self);
                let mut values = Vec::with_capacity(arguments.len());
                for argument in arguments {
                    let val = self.eval_expr(argument, env, call_depth)?;
                    self.push_temporary_root(val.clone());
                    values.push(val);
                }
                let result =
                    crate::tensor_dispatch::call(function_id, values.clone(), &self.tensors)
                        .map_err(|error| error.with_source_location(source_span.as_ref()))?;
                if self.trace_enabled && !self.trace_suppressed.get() {
                    let mut trace = self.tensor_trace.borrow_mut();
                    let ordinal = trace.len() + 1;
                    let inputs: Vec<_> = values
                        .iter()
                        .map(|value| tensor_trace_value(value, &self.tensors.borrow()))
                        .collect();
                    let event = serde_json::json!({
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
                    });
                    if self.reserve_trace(&event).is_some() {
                        trace.push(event);
                    }
                }
                Ok(result)
            }
            Expr::CallVision {
                function_id,
                arguments,
                ..
            } => {
                let _guard = TempRootGuard::new(self);
                let mut values = Vec::with_capacity(arguments.len());
                for argument in arguments {
                    let val = self.eval_expr(argument, env, call_depth)?;
                    self.push_temporary_root(val.clone());
                    values.push(val);
                }
                let (result, trace) = crate::vision_dispatch::call(
                    function_id,
                    &values,
                    &self.resource_root,
                    self.filesystem_read,
                    self.filesystem_write,
                )?;
                if self.reserve_trace(&trace).is_some() {
                    self.vision_trace.borrow_mut().push(trace);
                }
                Ok(result)
            }
            Expr::CallRuo {
                function_id,
                arguments,
                ..
            } => {
                let _guard = TempRootGuard::new(self);
                let mut values = Vec::with_capacity(arguments.len());
                for argument in arguments {
                    let val = self.eval_expr(argument, env, call_depth)?;
                    self.push_temporary_root(val.clone());
                    values.push(val);
                }
                let result = crate::ruo_dispatch::call(function_id, values.clone())?;
                for value in &values {
                    if matches!(value, Value::ReasonObject(_) | Value::ReasonTransaction(_)) {
                        self.trace_mutation(value, &[], None, value);
                    }
                    if let Value::ReasonTransaction(transaction) = value {
                        let owner =
                            Value::ReasonObject(transaction.borrow().snapshot.owner.clone());
                        self.trace_mutation(&owner, &[], None, &owner);
                    }
                }
                Ok(result)
            }
            Expr::CallOptimizer {
                function_id,
                arguments,
                source_span,
            } => {
                let _guard = TempRootGuard::new(self);
                let mut values = Vec::with_capacity(arguments.len());
                for argument in arguments {
                    let val = self.eval_expr(argument, env, call_depth)?;
                    self.push_temporary_root(val.clone());
                    values.push(val);
                }
                crate::optimizer_dispatch::call(function_id, values, &self.tensors)
                    // Optimizer dispatch previously discarded the expression
                    // span, making TSF-001 impossible to locate in source.
                    .map_err(|error| {
                        RuntimeError::new(
                            &error.code,
                            format!("{} (while executing {function_id})", error.message),
                        )
                        .with_source_location(source_span.as_ref())
                    })
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
                if self.reserve_trace(&outcome.trace).is_some() {
                    self.reasoning_trace.borrow_mut().push(outcome.trace);
                }
                Ok(Value::Json(Rc::new(outcome.value)))
            }
            Expr::CallRelation {
                function_id,
                arguments,
                ..
            } => {
                bump(&self.metrics.relation_dispatch_count);
                let is_count = function_id == "relation.count";
                if is_count {
                    bump(&self.metrics.relation_count_count);
                }
                let _guard = TempRootGuard::new(self);
                let mut values = Vec::with_capacity(arguments.len());
                for argument in arguments {
                    let val = self.eval_expr(argument, env, call_depth)?;
                    self.push_temporary_root(val.clone());
                    values.push(val);
                }
                let timer = self.profile_start();
                if is_count && values.len() == 1 {
                    if let Value::CandidateSpace(space) = &values[0] {
                        // Spec section 17: exact symbolic count or nothing;
                        // never a hidden scan. A fused constraint (spec
                        // ReasonScript_Constraint_Fusion_v0_1) is already
                        // folded into `unvisited_count`'s generator-level
                        // accounting, so only a residual constraint blocks
                        // an exact count.
                        let space = space.borrow();
                        if !space.residual_constraints.is_empty() {
                            return Err(RuntimeError::new(
                                "CS-COUNT-001",
                                "relation.count on a constrained candidate space is not symbolically computable; use candidate_space.materialize(space).length for an explicit scan",
                            ));
                        }
                        self.profile_stop(timer, &self.metrics.relation_execution_ns);
                        return Ok(Value::Int(space.unvisited_count() as i64));
                    }
                }
                if is_count && self.fast_path && values.len() == 1 {
                    // P0-3 `relation.count` -> ARRAY_LEN Fast Path.
                    // ponytail: trusts the type checker's homogeneous `[Struct]`
                    // arrays and type-checks only the first element; the
                    // Generic Path below scans every row before counting.
                    if let Value::Array(items) = &values[0] {
                        let items = items.borrow();
                        if items
                            .first()
                            .is_none_or(|item| matches!(item, Value::Struct(_)))
                        {
                            bump(&self.metrics.fast_path_count);
                            self.profile_stop(timer, &self.metrics.relation_execution_ns);
                            return Ok(Value::Int(items.len() as i64));
                        }
                    }
                }
                let result = crate::relation_dispatch::call(function_id, values);
                self.profile_stop(timer, &self.metrics.relation_execution_ns);
                result
            }
            Expr::RelationFilter {
                source,
                binding,
                predicate,
                ..
            } => {
                validate_predicate(predicate)?;
                bump(&self.metrics.relation_dispatch_count);
                bump(&self.metrics.relation_filter_count);
                let source = self.eval_expr(source, env, call_depth)?;
                if let Value::CandidateSpace(space) = &source {
                    // Spec sections 18-19: a filter over a candidate space is
                    // lowered to a constraint addition, not a scan.
                    let constraint = compile_constraint(predicate, binding, &env.borrow())
                        .ok_or_else(|| {
                            RuntimeError::new(
                                "CS-PRED-001",
                                "relation predicate cannot be lowered to a symbolic candidate constraint (supported: comparisons of the row or `row % m` against Int captures, &&, ||, !); materialize the space first",
                            )
                        })?;
                    let timer = self.profile_start();
                    let result = self.candidate_with_constraint(space, constraint);
                    self.profile_stop(timer, &self.metrics.relation_execution_ns);
                    return result;
                }
                let Value::Array(rows) = source else {
                    return Err(RuntimeError::new(
                        "REL-004",
                        "Relation function requires Array<Struct>",
                    ));
                };
                let relation_timer = self.profile_start();
                let fast = if self.fast_path {
                    compile_fast_predicate(predicate, binding, &env.borrow())
                } else {
                    None
                };
                let recording = self.recording_events();
                let rows = rows.borrow();
                let mut kept = Vec::with_capacity(rows.len());
                let mut removed: Vec<usize> = Vec::new();
                let mut removed_count = 0usize;
                // The row binding lives in the caller's frame for the duration
                // of the scan and is restored afterwards, instead of cloning
                // the entire environment per call (P0-6). A predicate cannot
                // assign, so nothing else in the frame can change meanwhile.
                let saved = env.borrow_mut().remove(binding);
                let predicate_timer = self.profile_start();
                let mut outcome: Result<(), RuntimeError> = Ok(());
                for (index, row) in rows.iter().enumerate() {
                    if !matches!(row, Value::Struct(_)) {
                        outcome = Err(RuntimeError::new(
                            "REL-004",
                            "Relation function requires Array<Struct>",
                        ));
                        break;
                    }
                    self.relation_rows_scanned
                        .set(self.relation_rows_scanned.get() + 1);
                    bump(&self.metrics.relation_predicate_eval_count);
                    let reads = &self.metrics.struct_field_read_count;
                    let verdict = match fast.as_ref().and_then(|fast| fast.eval(row, reads)) {
                        Some(verdict) => {
                            bump(&self.metrics.fast_path_count);
                            Ok(verdict)
                        }
                        None => {
                            {
                                let mut env_mut = env.borrow_mut();
                                match env_mut.get_mut(binding) {
                                    Some(slot) => *slot = row.clone(),
                                    None => {
                                        env_mut.insert(binding.clone(), row.clone());
                                    }
                                }
                            }
                            match self.eval_expr(predicate, env, call_depth) {
                                Ok(Value::Bool(verdict)) => Ok(verdict),
                                Ok(_) => Err(RuntimeError::new(
                                    "REL-PRED-003",
                                    "relation predicate must return Bool",
                                )),
                                Err(error) => Err(error),
                            }
                        }
                    };
                    match verdict {
                        Ok(true) => kept.push(row.clone()),
                        Ok(false) => {
                            removed_count += 1;
                            if recording {
                                removed.push(index);
                            }
                        }
                        Err(error) => {
                            outcome = Err(error);
                            break;
                        }
                    }
                }
                self.profile_stop(predicate_timer, &self.metrics.predicate_execution_ns);
                {
                    let mut env_mut = env.borrow_mut();
                    match saved {
                        Some(value) => {
                            env_mut.insert(binding.clone(), value);
                        }
                        None => {
                            env_mut.remove(binding);
                        }
                    }
                }
                outcome?;
                if removed_count > 0 {
                    self.metrics
                        .candidate_pruned_count
                        .set(self.metrics.candidate_pruned_count.get() + removed_count as u64);
                    let before_count = rows.len();
                    let after_count = kept.len();
                    self.semantic_event("CANDIDATE_PRUNED", || {
                        (
                            serde_json::json!(binding),
                            serde_json::Value::Null,
                            serde_json::json!(removed),
                            serde_json::json!({
                                "before_count": before_count,
                                "after_count": after_count,
                                "removed_count": removed_count,
                            }),
                        )
                    })?;
                }
                self.profile_stop(relation_timer, &self.metrics.relation_execution_ns);
                Ok(Value::Array(Rc::new(RefCell::new(kept))))
            }
            Expr::ArrayBuilder { .. } => Ok(Value::ArrayBuilder(Rc::new(RefCell::new(
                crate::value::ArrayBuilder {
                    items: Some(Vec::new()),
                },
            )))),
            Expr::CallArrayBuilder {
                builder,
                method,
                arguments,
                ..
            } => {
                let _guard = TempRootGuard::new(self);
                let owner = self.eval_expr(builder, env, call_depth)?;
                self.push_temporary_root(owner.clone());
                let Value::ArrayBuilder(builder) = &owner else {
                    return Err(RuntimeError::new(
                        "COLL-004",
                        "builder method requires an ArrayBuilder",
                    ));
                };
                if builder.borrow().items.is_none() {
                    return Err(RuntimeError::new(
                        "COLL-005",
                        "ArrayBuilder has already been finished",
                    ));
                }
                match (method.as_str(), arguments.as_slice()) {
                    ("append", [item]) => {
                        let value = self.eval_expr(item, env, call_depth)?.deep_clone();
                        // Evaluating the item can finish an alias of this builder.
                        let length = builder
                            .borrow()
                            .items
                            .as_ref()
                            .ok_or_else(|| {
                                RuntimeError::new(
                                    "COLL-005",
                                    "ArrayBuilder has already been finished",
                                )
                            })?
                            .len()
                            + 1;
                        self.trace_mutation(
                            &owner,
                            &["array_builder".to_owned(), "length".to_owned()],
                            None,
                            &Value::Int(length as i64),
                        );
                        builder.borrow_mut().items.as_mut().unwrap().push(value);
                        self.builder_appends.set(self.builder_appends.get() + 1);
                        bump(&self.metrics.array_write_count);
                        Ok(Value::Null)
                    }
                    ("finish", []) => {
                        self.trace_mutation(
                            &owner,
                            &["array_builder".to_owned(), "length".to_owned()],
                            None,
                            &Value::Int(0),
                        );
                        self.trace_mutation(
                            &owner,
                            &["array_builder".to_owned(), "finished".to_owned()],
                            None,
                            &Value::Bool(true),
                        );
                        let items = builder.borrow_mut().items.take().unwrap();
                        Ok(Value::Array(Rc::new(RefCell::new(items))))
                    }
                    _ => Err(RuntimeError::new(
                        "COLL-001",
                        "invalid builder method or argument count",
                    )),
                }
            }
            Expr::CallCandidateSpace {
                function_id,
                arguments,
                source_span,
            } => self
                .call_candidate_space(function_id, arguments, env, call_depth)
                .map_err(|error| error.with_source_location(source_span.as_ref())),
            Expr::CallSemanticEvent {
                function_id,
                arguments,
                ..
            } => {
                if function_id != "reasoning.event" || arguments.len() != 3 {
                    return Err(RuntimeError::new(
                        "REASON-EVENT-001",
                        "reasoning.event expects type, subject, evidence",
                    ));
                }
                // No argument vector: a `reasoning.event` call in `count`
                // mode must not allocate (spec v0.1 section 24 -- the
                // per-hypothesis event is the only remaining per-candidate
                // work in a lazy search).
                let _guard = TempRootGuard::new(self);
                let event_type = self.eval_expr(&arguments[0], env, call_depth)?;
                let subject = self.eval_expr(&arguments[1], env, call_depth)?;
                self.push_temporary_root(subject.clone());
                let evidence = self.eval_expr(&arguments[2], env, call_depth)?;
                self.push_temporary_root(evidence.clone());
                let Value::String(event_type) = &event_type else {
                    return Err(RuntimeError::new(
                        "REASON-EVENT-001",
                        "event type must be a string",
                    ));
                };
                self.semantic_event(event_type, || {
                    (
                        to_json(&subject),
                        to_json(&evidence),
                        serde_json::json!([]),
                        serde_json::json!({}),
                    )
                })
            }
            Expr::CallArrayAppend {
                collection, item, ..
            } => {
                let _guard = TempRootGuard::new(self);
                let collection_value = self.eval_expr(collection, env, call_depth)?;
                self.push_temporary_root(collection_value.clone());
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
            Expr::CallArrayConcat { left, right, .. } => {
                let _guard = TempRootGuard::new(self);
                let left_value = self.eval_expr(left, env, call_depth)?;
                self.push_temporary_root(left_value.clone());
                let right_value = self.eval_expr(right, env, call_depth)?;
                match (left_value, right_value) {
                    (Value::Array(left_items), Value::Array(right_items)) => {
                        let mut new_items = left_items.borrow().clone();
                        new_items.extend(right_items.borrow().iter().cloned());
                        Ok(Value::Array(Rc::new(RefCell::new(new_items))))
                    }
                    (left, right) => Err(RuntimeError::new(
                        "RT-CALL-006",
                        format!(
                            "array.concat arguments must be arrays, got {} and {}",
                            left.type_name(),
                            right.type_name()
                        ),
                    )),
                }
            }
            Expr::CallString {
                function_id,
                arguments,
                ..
            } => {
                let _guard = TempRootGuard::new(self);
                let mut values = Vec::with_capacity(arguments.len());
                for argument in arguments {
                    let val = self.eval_expr(argument, env, call_depth)?;
                    self.push_temporary_root(val.clone());
                    values.push(val);
                }
                crate::string_dispatch::call(function_id, values)
            }
            Expr::CallConsole {
                function_id,
                arguments,
                ..
            } => {
                let _guard = TempRootGuard::new(self);
                let mut values = Vec::with_capacity(arguments.len());
                for argument in arguments {
                    let val = self.eval_expr(argument, env, call_depth)?;
                    self.push_temporary_root(val.clone());
                    values.push(val);
                }
                crate::console_dispatch::dispatch(function_id, &values, &self.console_events)
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
            Expr::EnumValue {
                enum_name,
                variant_name,
                ..
            } => Ok(Value::Enum {
                enum_name: Rc::from(enum_name.as_str()),
                variant_name: Rc::from(variant_name.as_str()),
            }),
            Expr::OptionalSome { value, .. } => {
                let inner = self.eval_expr(value, env, call_depth)?;
                Ok(Value::Optional(Some(Box::new(inner))))
            }
            Expr::OptionalNone { .. } => Ok(Value::Optional(None)),
            Expr::Assert { condition, .. } => match self.eval_expr(condition, env, call_depth)? {
                Value::Bool(true) => Ok(Value::Null),
                Value::Bool(false) => Err(RuntimeError::new("TEST-ASSERT-001", "assertion failed")),
                other => Err(RuntimeError::new(
                    "RT-TYPE-001",
                    format!("assert() argument must be Bool, got {}", other.type_name()),
                )),
            },
            Expr::AssertEq {
                actual, expected, ..
            } => {
                let _guard = TempRootGuard::new(self);
                let actual_value = self.eval_expr(actual, env, call_depth)?;
                self.push_temporary_root(actual_value.clone());
                let expected_value = self.eval_expr(expected, env, call_depth)?;
                if actual_value == expected_value {
                    Ok(Value::Null)
                } else {
                    Err(RuntimeError::new(
                        "TEST-ASSERT-001",
                        format!("assertion failed: expected {expected_value}, got {actual_value}"),
                    ))
                }
            }
        }
    }

    fn call_function(
        &self,
        name: &str,
        argument_exprs: &[Expr],
        env: &Rc<RefCell<Env>>,
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
        let _args_guard = TempRootGuard::new(self);
        let mut arguments = Vec::with_capacity(argument_exprs.len());
        for argument_expr in argument_exprs {
            let val = self.eval_expr(argument_expr, env, call_depth)?;
            self.push_temporary_root(val.clone());
            arguments.push(val);
        }
        let mut local_env: Env = self.reason_objects.borrow().clone();
        local_env.extend(self.reasoning_bindings.clone());
        local_env.extend(function.parameters.iter().cloned().zip(arguments));
        let local_env = Rc::new(RefCell::new(local_env));
        let outcome = self.run_function(function, &local_env, call_depth + 1)?;
        match outcome {
            Outcome::Return(value) => {
                self.push_temporary_root(value.clone());
                Ok(value)
            }
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

fn trace_env(env: &Env) -> serde_json::Value {
    let mut visible = std::collections::BTreeMap::new();
    for (name, value) in env {
        if name.starts_with("__for_") || name.starts_with("__trace_") || name.starts_with("__opt_")
        {
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

fn collect_tensor_ids(
    value: &Value,
    roots: &mut std::collections::HashSet<String>,
    visited_arrays: &mut std::collections::HashSet<usize>,
    visited_structs: &mut std::collections::HashSet<usize>,
) {
    match value {
        Value::Tensor(id) => {
            roots.insert(id.to_string());
        }
        Value::Array(items) => {
            let ptr = Rc::as_ptr(items) as usize;
            if visited_arrays.insert(ptr) {
                for item in items.borrow().iter() {
                    collect_tensor_ids(item, roots, visited_arrays, visited_structs);
                }
            }
        }
        Value::ArrayBuilder(builder) => {
            let ptr = Rc::as_ptr(builder) as usize;
            if visited_arrays.insert(ptr) {
                if let Some(items) = &builder.borrow().items {
                    for item in items {
                        collect_tensor_ids(item, roots, visited_arrays, visited_structs);
                    }
                }
            }
        }
        Value::Optional(Some(value)) => {
            collect_tensor_ids(value, roots, visited_arrays, visited_structs);
        }
        Value::Struct(value) => {
            let ptr = Rc::as_ptr(value) as usize;
            if visited_structs.insert(ptr) {
                for item in value.fields.borrow().values() {
                    collect_tensor_ids(item, roots, visited_arrays, visited_structs);
                }
            }
        }
        _ => {}
    }
}

/// P0-4 predicate Fast Path for `relation.filter`: `row.field <op> value`,
/// `row.field % m <op> value`, combined with `&&`, `||` and `!`. Compiled
/// once per `relation.filter` call against the caller's environment (a
/// predicate cannot assign, so every captured local is stable for the whole
/// scan). Any row that leaves the happy path -- a non-Struct row, a missing
/// field, a non-Int modulo operand, incomparable operand types -- yields
/// `None` and is re-evaluated by the Generic Path, so results and
/// diagnostics are identical by construction.
enum FastOperand {
    Field(String),
    FieldModulo(String, i64),
    /// A captured struct's field (`state.value`), resolved once per scan but
    /// still counted as one field read per row, like the Generic Path.
    CapturedField(Value),
    Const(Value),
}

enum FastPredicate {
    Compare {
        operator: String,
        left: FastOperand,
        right: FastOperand,
    },
    And(Box<FastPredicate>, Box<FastPredicate>),
    Or(Box<FastPredicate>, Box<FastPredicate>),
    Not(Box<FastPredicate>),
}

fn compile_fast_predicate(expr: &Expr, binding: &str, env: &Env) -> Option<FastPredicate> {
    match expr {
        Expr::Comparison {
            operator,
            left,
            right,
            ..
        } => Some(FastPredicate::Compare {
            operator: operator.clone(),
            left: compile_fast_operand(left, binding, env)?,
            right: compile_fast_operand(right, binding, env)?,
        }),
        Expr::Logical {
            operator,
            left,
            right,
            ..
        } => {
            let left = Box::new(compile_fast_predicate(left, binding, env)?);
            let right = Box::new(compile_fast_predicate(right, binding, env)?);
            match operator.as_str() {
                "And" => Some(FastPredicate::And(left, right)),
                "Or" => Some(FastPredicate::Or(left, right)),
                _ => None,
            }
        }
        Expr::Unary {
            operator, operand, ..
        } if operator == "Not" => Some(FastPredicate::Not(Box::new(compile_fast_predicate(
            operand, binding, env,
        )?))),
        _ => None,
    }
}

fn compile_fast_operand(expr: &Expr, binding: &str, env: &Env) -> Option<FastOperand> {
    match expr {
        Expr::Member { object, member, .. } => match object.as_ref() {
            Expr::Local { name, .. } if name == binding => Some(FastOperand::Field(member.clone())),
            // `state.value`: a captured struct's field, read once per scan.
            Expr::Local { name, .. } => match env.get(name)? {
                Value::Struct(owner) => owner
                    .fields
                    .borrow()
                    .get(member)
                    .cloned()
                    .map(FastOperand::CapturedField),
                _ => None,
            },
            _ => None,
        },
        Expr::Const { kind, value, .. } => const_value(kind, value).ok().map(FastOperand::Const),
        Expr::Local { name, .. } if name != binding => {
            env.get(name).cloned().map(FastOperand::Const)
        }
        Expr::Binary {
            operator,
            left,
            right,
            ..
        } if operator == "Modulo" => {
            let FastOperand::Field(field) = compile_fast_operand(left, binding, env)? else {
                return None;
            };
            match compile_fast_operand(right, binding, env)? {
                FastOperand::Const(Value::Int(modulus)) if modulus != 0 => {
                    Some(FastOperand::FieldModulo(field, modulus))
                }
                _ => None,
            }
        }
        _ => None,
    }
}

impl FastOperand {
    /// `reads` is the VM's `struct_field_read_count`, kept in step with the
    /// Generic Path so counters are identical whichever path ran.
    #[inline]
    fn eval(&self, fields: &Env, reads: &Cell<u64>) -> Option<Value> {
        match self {
            FastOperand::Field(name) => {
                bump(reads);
                fields.get(name).cloned()
            }
            FastOperand::FieldModulo(name, modulus) => {
                bump(reads);
                match fields.get(name) {
                    Some(Value::Int(value)) => Some(Value::Int(python_mod_i64(*value, *modulus))),
                    _ => None,
                }
            }
            FastOperand::CapturedField(value) => {
                bump(reads);
                Some(value.clone())
            }
            FastOperand::Const(value) => Some(value.clone()),
        }
    }
}

impl FastPredicate {
    #[inline]
    fn eval(&self, row: &Value, reads: &Cell<u64>) -> Option<bool> {
        let Value::Struct(row) = row else {
            return None;
        };
        let fields = row.fields.borrow();
        self.eval_fields(&fields, reads)
    }

    fn eval_fields(&self, fields: &Env, reads: &Cell<u64>) -> Option<bool> {
        match self {
            FastPredicate::Compare {
                operator,
                left,
                right,
            } => match eval_comparison(
                operator,
                left.eval(fields, reads)?,
                right.eval(fields, reads)?,
            ) {
                Ok(Value::Bool(verdict)) => Some(verdict),
                _ => None,
            },
            // Same short-circuit as `Expr::Logical`: the right side is never
            // evaluated (and can never raise) when the left side decides.
            FastPredicate::And(left, right) => {
                if !left.eval_fields(fields, reads)? {
                    return Some(false);
                }
                right.eval_fields(fields, reads)
            }
            FastPredicate::Or(left, right) => {
                if left.eval_fields(fields, reads)? {
                    return Some(true);
                }
                right.eval_fields(fields, reads)
            }
            FastPredicate::Not(inner) => inner.eval_fields(fields, reads).map(|verdict| !verdict),
        }
    }
}

/// Lowers a `relation.filter` predicate over a candidate space to a
/// symbolic constraint (spec sections 19-20). The row binding is the
/// candidate value itself; captured locals and `state.field` reads are
/// resolved once, when the filter runs. `None` means the predicate has no
/// symbolic form (the caller reports `CS-PRED-001`).
fn compile_constraint(expr: &Expr, binding: &str, env: &Env) -> Option<Constraint> {
    match expr {
        Expr::Comparison {
            operator,
            left,
            right,
            ..
        } => {
            let op = CmpOp::parse(operator)?;
            if let Some(operand) = compile_row_operand(left, binding, env) {
                Some(operand.compare(op, compile_captured_int(right, binding, env)?))
            } else {
                let operand = compile_row_operand(right, binding, env)?;
                Some(operand.compare(op.flip(), compile_captured_int(left, binding, env)?))
            }
        }
        Expr::Logical {
            operator,
            left,
            right,
            ..
        } => {
            let left = Box::new(compile_constraint(left, binding, env)?);
            let right = Box::new(compile_constraint(right, binding, env)?);
            match operator.as_str() {
                "And" => Some(Constraint::And(left, right)),
                "Or" => Some(Constraint::Or(left, right)),
                _ => None,
            }
        }
        Expr::Unary {
            operator, operand, ..
        } if operator == "Not" => Some(compile_constraint(operand, binding, env)?.negated()),
        _ => None,
    }
}

enum RowOperand {
    Value,
    Modulo(i64),
}

impl RowOperand {
    fn compare(self, op: CmpOp, k: i64) -> Constraint {
        match self {
            RowOperand::Value => Constraint::Compare { op, k },
            RowOperand::Modulo(m) => Constraint::Modulo { m, op, r: k },
        }
    }
}

fn compile_row_operand(expr: &Expr, binding: &str, env: &Env) -> Option<RowOperand> {
    match expr {
        Expr::Local { name, .. } if name == binding => Some(RowOperand::Value),
        Expr::Binary {
            operator,
            left,
            right,
            ..
        } if operator == "Modulo" => {
            if !matches!(left.as_ref(), Expr::Local { name, .. } if name == binding) {
                return None;
            }
            match compile_captured_int(right, binding, env)? {
                0 => None,
                m => Some(RowOperand::Modulo(m)),
            }
        }
        _ => None,
    }
}

fn compile_captured_int(expr: &Expr, binding: &str, env: &Env) -> Option<i64> {
    match expr {
        Expr::Const { kind, value, .. } if kind == "int" => value.as_i64(),
        Expr::Local { name, .. } if name != binding => match env.get(name)? {
            Value::Int(value) => Some(*value),
            _ => None,
        },
        Expr::Member { object, member, .. } => match object.as_ref() {
            Expr::Local { name, .. } if name != binding => match env.get(name)? {
                Value::Struct(owner) => match owner.fields.borrow().get(member)? {
                    Value::Int(value) => Some(*value),
                    _ => None,
                },
                _ => None,
            },
            _ => None,
        },
        _ => None,
    }
}

fn validate_predicate(expression: &Expr) -> Result<(), RuntimeError> {
    match expression {
        Expr::Const { .. } | Expr::Local { .. } => Ok(()),
        Expr::Unary { operand, .. } => validate_predicate(operand),
        Expr::Binary { left, right, .. }
        | Expr::Comparison { left, right, .. }
        | Expr::Logical { left, right, .. } => {
            validate_predicate(left)?;
            validate_predicate(right)
        }
        Expr::Member { object, .. } => validate_predicate(object),
        Expr::Index {
            collection, index, ..
        } => {
            validate_predicate(collection)?;
            validate_predicate(index)
        }
        _ => Err(RuntimeError::new(
            "REL-PRED-002",
            "calls and side effects are not allowed in a relation predicate",
        )),
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

/// Structurally matches `value` against a `match` terminator arm's
/// `Pattern`. Returns the bindings a successful match would introduce
/// (possibly empty), or `None` if `pattern` does not match `value`.
/// Mirrors `_match_pattern_json` in `frontend/computation_ir/interpreter.py`
/// -- the two must agree on every pattern kind for the Python-vs-Rust
/// parity gate (`test_computation_ir_rust_parity.py`) to hold. Language
/// surface validation already guarantees a `match` statement is
/// exhaustive before this IR is ever produced, so a fully-exhausted arm
/// list (the `RT-MATCH-001` case in the caller) is a defensive fallback,
/// not an expected outcome.
fn match_pattern(pattern: &Pattern, value: &Value) -> Option<Vec<(String, Value)>> {
    match pattern {
        Pattern::Wildcard => Some(Vec::new()),
        Pattern::Binding { name } => Some(vec![(name.clone(), value.clone())]),
        Pattern::Literal {
            value_kind,
            value: literal,
        } => {
            let literal_value = const_value(value_kind, literal).ok()?;
            if &literal_value == value {
                Some(Vec::new())
            } else {
                None
            }
        }
        Pattern::Range {
            lower,
            upper,
            lower_inclusive,
            upper_inclusive,
        } => {
            let subject = match value {
                Value::Int(v) => *v as f64,
                Value::Float(v) => *v,
                _ => return None,
            };
            let lower = lower.as_f64()?;
            let upper = upper.as_f64()?;
            let lower_ok = if *lower_inclusive {
                subject >= lower
            } else {
                subject > lower
            };
            let upper_ok = if *upper_inclusive {
                subject <= upper
            } else {
                subject < upper
            };
            if lower_ok && upper_ok {
                Some(Vec::new())
            } else {
                None
            }
        }
        Pattern::EnumValue {
            enum_name,
            variant_name,
        } => match value {
            Value::Enum {
                enum_name: value_enum,
                variant_name: value_variant,
            } if value_enum.as_ref() == enum_name.as_str()
                && value_variant.as_ref() == variant_name.as_str() =>
            {
                Some(Vec::new())
            }
            _ => None,
        },
        Pattern::OptionalSome { pattern } => match value {
            Value::Optional(Some(inner)) => match_pattern(pattern, inner),
            _ => None,
        },
        Pattern::OptionalNone => match value {
            Value::Optional(None) => Some(Vec::new()),
            _ => None,
        },
        Pattern::Struct { type_name, fields } => match value {
            Value::Struct(struct_value) if &struct_value.type_name == type_name => {
                let mut bindings = Vec::new();
                let struct_fields = struct_value.fields.borrow();
                for (field_name, field_pattern) in fields {
                    let field_value = struct_fields.get(field_name)?;
                    bindings.extend(match_pattern(field_pattern, field_value)?);
                }
                Some(bindings)
            }
            _ => None,
        },
        Pattern::Or { alternatives } => alternatives
            .iter()
            .find_map(|alternative| match_pattern(alternative, value)),
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

    /// Like `run`, but executes on a thread with an explicit, large
    /// stack, and returns JSON instead of `Value` -- needed only for the
    /// deep-recursion tests below. `Value` holds `Rc`, which isn't
    /// `Send`, so results can't cross a `thread::spawn`/`.join()`
    /// boundary directly; converting to `serde_json::Value` (fully
    /// owned, no `Rc`) inside the worker thread before it returns
    /// sidesteps that.
    ///
    /// This exists because `cargo test`'s own per-test thread stack is
    /// markedly smaller than a real process's main thread (how
    /// `reason-runtime-host` is actually invoked, where the OS default
    /// already comfortably covers `max_call_depth`'s 128-level default)
    /// -- without it, `unbounded_recursion_stops_at_max_call_depth_with_rt_call_003`
    /// below stack-overflows and aborts the whole test binary before the
    /// depth check ever fires, instead of exercising it. `runtime-cli`'s
    /// `main` defends against the same underlying risk in production the
    /// same way (see its `run_main` wrapper) -- the depth check is only
    /// the *actual*, deterministic limit if the executing thread has
    /// enough native stack to reach it without overflowing first.
    fn run_json_on_large_stack(source: &str) -> Result<serde_json::Value, String> {
        const STACK_SIZE: usize = 64 * 1024 * 1024;
        let source = source.to_string();
        std::thread::Builder::new()
            .stack_size(STACK_SIZE)
            .spawn(move || -> Result<serde_json::Value, String> {
                let results = run(&source).map_err(|error| error.code)?;
                let mut map = serde_json::Map::new();
                for (name, value) in results {
                    map.insert(name, to_json(&value));
                }
                Ok(serde_json::Value::Object(map))
            })
            .expect("failed to spawn test worker thread")
            .join()
            .expect("test worker thread panicked")
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

    #[test]
    fn caller_frame_tensor_survives_callee_collection() {
        let ir = r#"{
            "schema": "reason-computation-ir/0.1",
            "calculations": ["Answer"],
            "functions": [
                {
                    "id": "fn.Callee",
                    "parameters": ["x"],
                    "entry_block": "b1",
                    "blocks": [{
                        "id": "b1",
                        "instructions": [{
                            "op": "assign", "target": "c",
                            "expr": {
                                "op": "call_tensor", "function_id": "tensor.add",
                                "arguments": [
                                    {"op": "local", "name": "x"},
                                    {"op": "const", "kind": "float", "value": 10.0}
                                ]
                            }
                        }],
                        "terminator": {
                            "kind": "return",
                            "value": {"op": "local", "name": "c"}
                        }
                    }]
                },
                {
                    "id": "Answer",
                    "parameters": [],
                    "entry_block": "b1",
                    "blocks": [{
                        "id": "b1",
                        "instructions": [
                            {
                                "op": "assign", "target": "caller_tensor",
                                "expr": {
                                    "op": "call_tensor", "function_id": "tensor.create",
                                    "arguments": [
                                        {"op": "array", "elements": [
                                            {"op": "const", "kind": "float", "value": 5.0}
                                        ]},
                                        {"op": "const", "kind": "string", "value": "f64"}
                                    ]
                                }
                            },
                            {
                                "op": "assign", "target": "callee_res",
                                "expr": {
                                    "op": "call_function", "name": "Callee",
                                    "arguments": [
                                        {"op": "call_tensor", "function_id": "tensor.create",
                                         "arguments": [
                                             {"op": "array", "elements": [
                                                 {"op": "const", "kind": "float", "value": 1.0}
                                             ]},
                                             {"op": "const", "kind": "string", "value": "f64"}
                                         ]}
                                    ]
                                }
                            },
                            {
                                "op": "assign", "target": "final_tensor",
                                "expr": {
                                    "op": "call_tensor", "function_id": "tensor.add",
                                    "arguments": [
                                        {"op": "local", "name": "caller_tensor"},
                                        {"op": "local", "name": "callee_res"}
                                    ]
                                }
                            }
                        ],
                        "terminator": {
                            "kind": "result",
                            "value": {
                                "op": "call_tensor", "function_id": "tensor.to_array",
                                "arguments": [{"op": "local", "name": "final_tensor"}]
                            }
                        }
                    }]
                }
            ]
        }"#;
        let results = run(ir).expect("caller tensor must remain live");
        assert_eq!(results.len(), 1);
        match &results[0].1 {
            Value::Array(items) => {
                let items = items.borrow();
                assert_eq!(items.len(), 1);
                assert_eq!(items[0], Value::Float(16.0));
            }
            other => panic!("expected an array, got {other:?}"),
        }
    }

    #[test]
    fn enum_values_compare_by_name_not_by_string() {
        assert_eq!(
            Value::Enum {
                enum_name: Rc::from("Color"),
                variant_name: Rc::from("Red")
            },
            Value::Enum {
                enum_name: Rc::from("Color"),
                variant_name: Rc::from("Red")
            }
        );
        assert_ne!(
            Value::Enum {
                enum_name: Rc::from("Color"),
                variant_name: Rc::from("Red")
            },
            Value::Enum {
                enum_name: Rc::from("Color"),
                variant_name: Rc::from("Blue")
            }
        );
        assert_ne!(
            Value::Enum {
                enum_name: Rc::from("Color"),
                variant_name: Rc::from("Red")
            },
            Value::String(Rc::from("Red"))
        );
    }

    #[test]
    fn match_dispatches_on_enum_value_falling_through_to_wildcard() {
        let ir = r#"{
            "schema": "reason-computation-ir/0.2",
            "calculations": ["Answer"],
            "functions": [{
                "id": "Answer",
                "parameters": [],
                "entry_block": "b1",
                "blocks": [
                    {
                        "id": "b1",
                        "instructions": [{
                            "op": "assign", "target": "color",
                            "expr": {"op": "enum_value", "enum_name": "Color", "variant_name": "Green"}
                        }],
                        "terminator": {
                            "kind": "match",
                            "subject": {"op": "local", "name": "color"},
                            "arms": [
                                {
                                    "pattern": {"kind": "enum_value", "enum_name": "Color", "variant_name": "Red"},
                                    "guard": null,
                                    "target": "b_red"
                                },
                                {
                                    "pattern": {"kind": "wildcard"},
                                    "guard": null,
                                    "target": "b_default"
                                }
                            ]
                        }
                    },
                    {
                        "id": "b_red",
                        "instructions": [],
                        "terminator": {"kind": "result", "value": {"op": "const", "kind": "int", "value": 1}}
                    },
                    {
                        "id": "b_default",
                        "instructions": [],
                        "terminator": {"kind": "result", "value": {"op": "const", "kind": "int", "value": 0}}
                    }
                ]
            }]
        }"#;
        let results = run(ir).expect("no runtime error");
        assert_eq!(results, vec![("Answer".to_string(), Value::Int(0))]);
    }

    #[test]
    fn match_binds_optional_some_and_distinguishes_none_from_null() {
        let ir = r#"{
            "schema": "reason-computation-ir/0.2",
            "calculations": ["Some", "None"],
            "functions": [
                {
                    "id": "Some",
                    "parameters": [],
                    "entry_block": "b1",
                    "blocks": [
                        {
                            "id": "b1",
                            "instructions": [{
                                "op": "assign", "target": "value",
                                "expr": {"op": "optional_some", "value": {"op": "const", "kind": "int", "value": 42}}
                            }],
                            "terminator": {
                                "kind": "match",
                                "subject": {"op": "local", "name": "value"},
                                "arms": [
                                    {
                                        "pattern": {"kind": "optional_some", "pattern": {"kind": "binding", "name": "x"}},
                                        "guard": null,
                                        "target": "b_some"
                                    },
                                    {
                                        "pattern": {"kind": "optional_none"},
                                        "guard": null,
                                        "target": "b_none"
                                    }
                                ]
                            }
                        },
                        {
                            "id": "b_some",
                            "instructions": [],
                            "terminator": {"kind": "result", "value": {"op": "local", "name": "x"}}
                        },
                        {
                            "id": "b_none",
                            "instructions": [],
                            "terminator": {"kind": "result", "value": {"op": "const", "kind": "int", "value": -1}}
                        }
                    ]
                },
                {
                    "id": "None",
                    "parameters": [],
                    "entry_block": "b1",
                    "blocks": [
                        {
                            "id": "b1",
                            "instructions": [{
                                "op": "assign", "target": "value",
                                "expr": {"op": "optional_none"}
                            }],
                            "terminator": {
                                "kind": "match",
                                "subject": {"op": "local", "name": "value"},
                                "arms": [
                                    {
                                        "pattern": {"kind": "optional_some", "pattern": {"kind": "binding", "name": "x"}},
                                        "guard": null,
                                        "target": "b_some"
                                    },
                                    {
                                        "pattern": {"kind": "optional_none"},
                                        "guard": null,
                                        "target": "b_none"
                                    }
                                ]
                            }
                        },
                        {
                            "id": "b_some",
                            "instructions": [],
                            "terminator": {"kind": "result", "value": {"op": "local", "name": "x"}}
                        },
                        {
                            "id": "b_none",
                            "instructions": [],
                            "terminator": {"kind": "result", "value": {"op": "const", "kind": "int", "value": -1}}
                        }
                    ]
                }
            ]
        }"#;
        let results = run(ir).expect("no runtime error");
        assert_eq!(
            results,
            vec![
                ("Some".to_string(), Value::Int(42)),
                ("None".to_string(), Value::Int(-1)),
            ]
        );
    }

    #[test]
    fn match_guard_failure_rolls_back_pattern_bindings_before_trying_next_arm() {
        // Both arms bind the subject to `x`; the first arm's guard is
        // false, so its binding must be undone before the second arm's
        // guard runs -- otherwise a stale `x` from the failed first arm
        // could leak into the second arm's guard evaluation.
        let ir = r#"{
            "schema": "reason-computation-ir/0.2",
            "calculations": ["Answer"],
            "functions": [{
                "id": "Answer",
                "parameters": [],
                "entry_block": "b1",
                "blocks": [
                    {
                        "id": "b1",
                        "instructions": [],
                        "terminator": {
                            "kind": "match",
                            "subject": {"op": "const", "kind": "int", "value": 5},
                            "arms": [
                                {
                                    "pattern": {"kind": "binding", "name": "x"},
                                    "guard": {
                                        "op": "comparison", "operator": "GreaterThan",
                                        "left": {"op": "local", "name": "x"},
                                        "right": {"op": "const", "kind": "int", "value": 10}
                                    },
                                    "target": "b_big"
                                },
                                {
                                    "pattern": {"kind": "binding", "name": "x"},
                                    "guard": null,
                                    "target": "b_default"
                                }
                            ]
                        }
                    },
                    {
                        "id": "b_big",
                        "instructions": [],
                        "terminator": {"kind": "result", "value": {"op": "const", "kind": "int", "value": 1}}
                    },
                    {
                        "id": "b_default",
                        "instructions": [],
                        "terminator": {"kind": "result", "value": {"op": "local", "name": "x"}}
                    }
                ]
            }]
        }"#;
        let results = run(ir).expect("no runtime error");
        assert_eq!(results, vec![("Answer".to_string(), Value::Int(5))]);
    }

    #[test]
    fn direct_self_recursion_computes_correctly() {
        // Phase 4 ("制御された再帰"): a function calling itself is no
        // longer rejected at the language-surface level (FN-007 removed)
        // -- this proves the VM's own call-depth machinery (already
        // present for ordinary nested calls) handles a self-referential
        // `call_function` correctly, independent of the Python lowering
        // pipeline.
        let ir = r#"{
            "schema": "reason-computation-ir/0.2",
            "calculations": ["Answer"],
            "functions": [
                {
                    "id": "fn.Factorial",
                    "parameters": ["n"],
                    "entry_block": "b1",
                    "blocks": [
                        {
                            "id": "b1",
                            "instructions": [],
                            "terminator": {
                                "kind": "branch",
                                "condition": {
                                    "op": "comparison", "operator": "LessThanOrEqual",
                                    "left": {"op": "local", "name": "n"},
                                    "right": {"op": "const", "kind": "int", "value": 1}
                                },
                                "then": "b_base",
                                "else": "b_recurse"
                            }
                        },
                        {
                            "id": "b_base",
                            "instructions": [],
                            "terminator": {"kind": "return", "value": {"op": "const", "kind": "int", "value": 1}}
                        },
                        {
                            "id": "b_recurse",
                            "instructions": [],
                            "terminator": {
                                "kind": "return",
                                "value": {
                                    "op": "binary", "operator": "Multiply",
                                    "left": {"op": "local", "name": "n"},
                                    "right": {
                                        "op": "call_function", "name": "Factorial",
                                        "arguments": [{
                                            "op": "binary", "operator": "Subtract",
                                            "left": {"op": "local", "name": "n"},
                                            "right": {"op": "const", "kind": "int", "value": 1}
                                        }]
                                    }
                                }
                            }
                        }
                    ]
                },
                {
                    "id": "Answer",
                    "parameters": [],
                    "entry_block": "b1",
                    "blocks": [{
                        "id": "b1",
                        "instructions": [],
                        "terminator": {
                            "kind": "result",
                            "value": {
                                "op": "call_function", "name": "Factorial",
                                "arguments": [{"op": "const", "kind": "int", "value": 5}]
                            }
                        }
                    }]
                }
            ]
        }"#;
        let result = run_json_on_large_stack(ir).expect("no runtime error");
        assert_eq!(result["Answer"], serde_json::json!(120));
    }

    #[test]
    fn unbounded_recursion_stops_at_max_call_depth_with_rt_call_003() {
        let ir = r#"{
            "schema": "reason-computation-ir/0.2",
            "calculations": ["Answer"],
            "functions": [
                {
                    "id": "fn.Loop",
                    "parameters": ["n"],
                    "entry_block": "b1",
                    "blocks": [{
                        "id": "b1",
                        "instructions": [],
                        "terminator": {
                            "kind": "return",
                            "value": {
                                "op": "call_function", "name": "Loop",
                                "arguments": [{
                                    "op": "binary", "operator": "Add",
                                    "left": {"op": "local", "name": "n"},
                                    "right": {"op": "const", "kind": "int", "value": 1}
                                }]
                            }
                        }
                    }]
                },
                {
                    "id": "Answer",
                    "parameters": [],
                    "entry_block": "b1",
                    "blocks": [{
                        "id": "b1",
                        "instructions": [],
                        "terminator": {
                            "kind": "result",
                            "value": {
                                "op": "call_function", "name": "Loop",
                                "arguments": [{"op": "const", "kind": "int", "value": 0}]
                            }
                        }
                    }]
                }
            ]
        }"#;
        let error_code = run_json_on_large_stack(ir).expect_err("must fail");
        assert_eq!(error_code, "RT-CALL-003");
    }
}
