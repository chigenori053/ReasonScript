//! In-process profile harness for the reasoning-state hot path.
//!
//! ```text
//! cargo run --release -p reasonscript-computation-runtime-cli --example reasoning_state_profile \
//!     -- <program.json> <normal|ru_full|lightweight|causality|objects_rus|objects_ruo> [iterations]
//! ```
//!
//! Reports, per phase, the median time and the allocation count of executing the
//! program (`run`, the `runtime_execution_ns` boundary) and of building the state
//! artifacts and hashes (`materialize`, the response-construction phase). Attach
//! `sample <pid>` to it for a call-graph profile.

use reasonscript_computation_ir::reason_objects::ReasonObjectsMode;
use reasonscript_computation_ir::reason_structure::{ExecutableMode, ReasonUnitMode};
use reasonscript_computation_ir::reasoning_state::ReasoningStateMode;
use reasonscript_computation_ir::state_causality::StateCausalityMode;
use reasonscript_computation_ir::{decode, NumericMode, TensorPolicy, Vm};
use std::alloc::{GlobalAlloc, Layout, System};
use std::hint::black_box;
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::Instant;

struct Counting;
static ALLOCATIONS: AtomicU64 = AtomicU64::new(0);
/// Allocation-size histogram (power-of-two buckets), printed with `HISTOGRAM=1`.
static SIZES: [AtomicU64; 12] = [const { AtomicU64::new(0) }; 12];

fn bucket(size: usize) -> usize {
    (size.next_power_of_two().trailing_zeros() as usize).min(11)
}

unsafe impl GlobalAlloc for Counting {
    unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
        ALLOCATIONS.fetch_add(1, Ordering::Relaxed);
        SIZES[bucket(layout.size())].fetch_add(1, Ordering::Relaxed);
        System.alloc(layout)
    }
    unsafe fn dealloc(&self, ptr: *mut u8, layout: Layout) {
        System.dealloc(ptr, layout)
    }
    unsafe fn realloc(&self, ptr: *mut u8, layout: Layout, new_size: usize) -> *mut u8 {
        ALLOCATIONS.fetch_add(1, Ordering::Relaxed);
        System.realloc(ptr, layout, new_size)
    }
}

#[global_allocator]
static ALLOCATOR: Counting = Counting;

fn median(values: &mut [u64]) -> u64 {
    values.sort_unstable();
    values[values.len() / 2]
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let document: serde_json::Value =
        serde_json::from_str(&std::fs::read_to_string(&args[1]).unwrap()).unwrap();
    let program_value = document.get("program").unwrap_or(&document);
    let program = decode(&program_value.to_string()).unwrap();
    let config = args.get(2).map_or("causality", String::as_str);
    let iterations: usize = args.get(3).map_or(2000, |value| value.parse().unwrap());
    let objects = match config {
        "objects_rus" => ReasonObjectsMode::Rus,
        "objects_ruo" => ReasonObjectsMode::RusRuo,
        _ => ReasonObjectsMode::Off,
    };
    let (executable, state, causality) = match config {
        "normal" => (
            ExecutableMode::Off,
            ReasoningStateMode::Off,
            StateCausalityMode::Off,
        ),
        "ru_full" => (
            ExecutableMode::Full,
            ReasoningStateMode::Off,
            StateCausalityMode::Off,
        ),
        "lightweight" => (
            ExecutableMode::Full,
            ReasoningStateMode::Lightweight,
            StateCausalityMode::Off,
        ),
        "causality" | "objects_rus" | "objects_ruo" => (
            ExecutableMode::Full,
            ReasoningStateMode::Off,
            StateCausalityMode::Full,
        ),
        other => panic!("unknown config {other}"),
    };
    let (mut run_ns, mut run_allocs, mut materialize_ns, mut materialize_allocs) =
        (Vec::new(), Vec::new(), Vec::new(), Vec::new());
    let (mut objects_ns, mut objects_allocs) = (Vec::new(), Vec::new());
    let mut transitions = 0;
    for iteration in 0..iterations + iterations / 10 {
        let mut vm = Vm::with_runtime_context(
            &program,
            NumericMode::CompatReference,
            TensorPolicy::default(),
            ".".into(),
            false,
            false,
            false,
            "RuntimeReal".to_owned(),
            64,
            1_000_000,
        );
        vm.configure_reason_units(ReasonUnitMode::Off);
        vm.configure_executable_reason_units(executable);
        vm.configure_reasoning_state(state);
        vm.configure_state_causality(causality);
        vm.configure_reason_objects(objects);
        let allocations = ALLOCATIONS.load(Ordering::Relaxed);
        let started = Instant::now();
        black_box(vm.run_calculations(&program).unwrap());
        let elapsed = started.elapsed().as_nanos() as u64;
        let run_allocations = ALLOCATIONS.load(Ordering::Relaxed) - allocations;
        let allocations = ALLOCATIONS.load(Ordering::Relaxed);
        let started = Instant::now();
        let artifacts = (vm.state_causality_trace(), vm.reasoning_state_trace());
        // The response path numbers the state relations before the RUOs reference them.
        let objects_started = Instant::now();
        let objects_allocations = ALLOCATIONS.load(Ordering::Relaxed);
        let projected = objects.enabled().then(|| {
            let mut relations = artifacts.0.relations.clone();
            for (index, relation) in relations.iter_mut().enumerate() {
                relation.id = format!("causal-relation:{:08}", index + 1);
            }
            vm.reason_objects_trace(&relations)
        });
        let objects_elapsed = objects_started.elapsed().as_nanos() as u64;
        let objects_alloc = ALLOCATIONS.load(Ordering::Relaxed) - objects_allocations;
        let materialized = started.elapsed().as_nanos() as u64;
        let materialize_allocations = ALLOCATIONS.load(Ordering::Relaxed) - allocations;
        transitions = artifacts.1.revision;
        black_box((artifacts, projected));
        if iteration >= iterations / 10 {
            objects_ns.push(objects_elapsed);
            objects_allocs.push(objects_alloc);
            run_ns.push(elapsed);
            run_allocs.push(run_allocations);
            materialize_ns.push(materialized);
            materialize_allocs.push(materialize_allocations);
        }
    }
    if std::env::var_os("HISTOGRAM").is_some() {
        let per_run = iterations + iterations / 10;
        let sizes: Vec<_> = SIZES
            .iter()
            .map(|count| count.load(Ordering::Relaxed) / per_run as u64)
            .collect();
        eprintln!("allocations per iteration by size bucket (<=2^i bytes): {sizes:?}");
    }
    println!(
        "{}",
        serde_json::json!({
            "config": config,
            "iterations": iterations,
            "state_revisions": transitions,
            "run_ns": median(&mut run_ns),
            "run_allocations": median(&mut run_allocs),
            "materialize_ns": median(&mut materialize_ns),
            "materialize_allocations": median(&mut materialize_allocs),
            "objects_ns": median(&mut objects_ns),
            "objects_allocations": median(&mut objects_allocs),
        })
    );
}
