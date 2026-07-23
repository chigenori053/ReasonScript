# Runtime

ReasonScript ships three separate Rust crates under the umbrella term
"Runtime." They are not layers of one another — each is an independent
crate with its own `Cargo.toml` — and they are at very different levels of
maturity.

| Crate | Role | Maturity |
| --- | --- | --- |
| `RuntimeReal/` | Primary execution engine: state-first, transactional, implements Operational Semantics OS-01..OS-10 | Partially Complete (production path) |
| `HybridRuntime/` | Ambiguity resolution + the Semantic Language v0.2 engines (SP1-SP9), `ReasonGraph` | Partially Complete |
| `RuntimeComplex/` | Stub reserved for a future runtime specialization | Scaffold only, no real behavior |

A project selects its backend in `reason.toml`:

```toml
[runtime]
backend = "RuntimeReal"
```

`reason run` (`toolchain/run_cmd.py`) reads this and dispatches to the
matching backend through `frontend.runtime_integration`.

## RuntimeReal

The "state-first layered Hybrid Runtime" referenced in the platform release
docs. It owns the canonical transaction protocol:

```text
Prepare -> Validate -> Commit -> StateDelta
```

Only the State Kernel may mutate committed state; rollback replays a traced
*reverse* delta rather than editing history. Key modules:

- `src/core/` — `reason_unit.rs` (`ReasonUnit`, see
  [reasonunit.md](reasonunit.md)), `state.rs`, `transition.rs`,
  `type_system.rs`, `semantic_constraint.rs`, `structural_constraint.rs`
  (SCV-1).
- `src/graph/` — `reason_graph.rs`, `reasoning_space.rs` (the Reasoning
  Space of the Semantic Language v0.2 model).
- `src/executor/` — `executor.rs`, `scheduler.rs`, `convergence.rs`.
- `src/ir/` — includes the Tensor IR lowering stage, see
  [tensor.md](tensor.md).
- `src/knowledge/` — Knowledge emergence (KEV-1).
- `src/storage/` — `checkpoint.rs`, `persistence.rs`.

Normative references: the state/transition/plan contract is
[ReasonScript_Operational_Semantics_v0.1.md](../specifications/ReasonScript_Operational_Semantics_v0.1.md);
platform-level completion status is
[Runtime_v0.1_Completion_Report.md](../specifications/Runtime_v0.1_Completion_Report.md)
and `docs/platform_architecture_review/runtime_review.md`.

## HybridRuntime

A complementary crate focused on resolving *ambiguous* state and on the
newer Semantic Language v0.2 pipeline (`SemanticUnit -> SemanticRelation ->
Reasoning Space -> SemanticPlan -> SemanticSimulation -> SimulationResult ->
Knowledge`). Given an uncertain `State`, its `DecisionEngine` picks among
three strategies — `RealStrategy`, `ClarifyStrategy`, `ComplexStrategy` — by
**minimum expected cost** under a `RiskPolicy`, not simple thresholding.

Key pieces:

- `HybridRuntime`, `HybridReasonUnit` (`src/state.rs`),
  `State`/`AmbiguousState`/`StableState`.
- `IdentityResolver`, `ReasonGraph`/`ReasonGraphRuntime`.
- `TransactionKernel` (`transaction.rs`): `PreparedDelta`,
  `ValidationChecks`, `ValidationStatus`.
- Reason IR types (`reason_ir.rs`): `ReasonIR`, `ExecutionPlan`,
  `StateKernel`, `Trace`, `InferenceResult`.
- Nine "semantic engines" (SP1-SP9), one module each: `semantic_type`,
  `semantic_constraint`, `semantic_closure`, `semantic_contradiction`,
  `semantic_similarity`, `semantic_transformation`, `semantic_planning`,
  `semantic_search`, `semantic_simulation`.

Normative reference:
[ReasonScript_Semantic_Language_Core_v0.2.md](../specifications/ReasonScript_Semantic_Language_Core_v0.2.md).

## RuntimeComplex

Crate name `reasonscript-runtime-complex`, depends on `num-complex`. Its
entire content today is a stub `ComplexReasonUnit { label: String }` struct
with one smoke test; `src/runtime/mod.rs` is empty. It exists as a reserved
namespace for a future complex-valued runtime variant — do not build on it
expecting real behavior yet.

## Legacy Prototype

`Legacy/elixir_runtime/` is an old Elixir/OTP-based runtime prototype
(`distributed_proof_barrier.ex`, `orchestrator_server.ex`,
`session_supervisor.ex`) explored before the current Rust runtimes. It is
historical context only, not part of the current architecture — see
[cluster-runtime.md](cluster-runtime.md) for why this matters when
evaluating distributed-execution claims.

## Runtime Correctness Invariants

Enforced across `RuntimeReal` and `HybridRuntime` alike (formalized as
OS-01..OS-10 in the Operational Semantics spec):

- Goal immutability and state identity stability.
- Constraint purity (constraints never mutate state).
- Plan immutability once an `ExecutionPlan` is produced.
- Delta traceability — every `StateDelta` carries enough trace to be
  reversed.
- Determinism and commit-only mutation (see
  [overview.md](overview.md#design-invariants)).
