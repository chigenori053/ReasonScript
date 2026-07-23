# Tensor (IR)

## Status: Implemented, as an internal IR stage — not a standalone product

There is no standalone "Tensor Runtime" module, SDK, or spec document.
What exists is a real, working numerical intermediate representation and
executor **inside `RuntimeReal`**: `ReasonGraph` lowers to `TensorIR`, which
is then executed as matrix operations. This page documents that IR stage
precisely so it isn't confused with a bigger product surface (like the
[WorldModel SDK](worldmodel.md), which *is* a standalone public API).

## Pipeline

```text
GraphIR  --(RuntimeReal/src/ir/lowering.rs: Lowering::lower)-->  TensorIR
TensorIR --(RuntimeReal/src/executor/executor.rs: Executor::execute)--> Array2<f64>
```

## Key Types

`RuntimeReal/src/ir/tensor_ir.rs`:

```rust
pub struct TensorIR {
    state_matrix: Array2<f64>,
    transition_ops: Vec<TensorOp>,
}

pub enum TensorOp {
    Add,
    Mul,
    Lerp,
}
```

Backed by the `ndarray` crate (see `RuntimeReal/Cargo.toml`). A `Tensor`
variant also exists in the core type enum
(`RuntimeReal/src/core/types.rs`), so `ReasonUnit` vectors (see
[reasonunit.md](reasonunit.md)) and Tensor IR share the same underlying
numeric representation.

## Execution and Convergence

- `Executor::execute(&TensorIR) -> Array2<f64>` — "Execute Tensor IR (lower
  level)," per its own doc comment.
- `Convergence::converge(ir, threshold, max_iters)`
  (`RuntimeReal/src/executor/convergence.rs`) — an iterative convergence
  loop over `TensorIR`, used where a transition needs to be applied
  repeatedly until the state matrix stabilizes within `threshold`.

## Why This Exists

[ReasonScript_Computation_Model_v0.1.md](../specifications/ReasonScript_Computation_Model_v0.1.md)
establishes that all mathematical computation (algebra, calculus, linear
algebra, trigonometry, multivariable calculus, abstract math) is represented
purely as `State --Transition--> State` chains — there is no special-cased
math evaluator. The Tensor IR is the concrete mechanism that makes this
efficient: instead of interpreting each `Transition` individually, a graph
of transitions is lowered once into a single matrix-operation program and
executed as such.

## Testing and Further Reading

- Tests: `RuntimeReal/tests/tensor_lowering_tests.rs`.
- Completion reports:
  [Runtime_v0.1_Completion_Report.md](../specifications/Runtime_v0.1_Completion_Report.md),
  [Phase_VS-1_Completion_Report.md](../specifications/Phase_VS-1_Completion_Report.md),
  [ReasonGraph_Graph_IR_Validation_Phase_2_Report.md](../specifications/ReasonGraph_Graph_IR_Validation_Phase_2_Report.md),
  [HRU_Phase_B_Multi_State_Transition_Validation_Report.md](../specifications/HRU_Phase_B_Multi_State_Transition_Validation_Report.md).

## If You Need "Tensor Runtime" as a Product

It doesn't exist as a separate surface today. The Tensor IR is reachable
only through `RuntimeReal`'s normal execution path (compile source ->
Reason IR -> ExecutionPlan -> `RuntimeReal` execution); there is no public
API to construct or run `TensorIR` directly outside of the runtime crate
itself.
