# Architecture Overview

Audience: system architects and researchers evaluating or extending
ReasonScript's implementation. For a user-facing introduction, start with
the [README](../../README.md) and [guides](../guides/) instead.

ReasonScript is a **state-first, deterministic reasoning platform**: a
language and runtime pair where every program is a typed graph of states and
transitions, every execution step is validated before it commits, and every
mutation produces a traceable, replayable delta. This document maps the
subsystems that implement that model and how they fit together.

## The Pipeline

```text
ReasonScript Source (.rsn)
  -> Surface AST            (frontend/language_surface/)
  -> Semantic AST           (frontend/ast/)
  -> Reason IR              (reason-ir/0.1, schemas/reason_ir.schema.json)
  -> ExecutionPlan          (immutable, produced by the planner)
  -> Runtime execution      (RuntimeReal / HybridRuntime)
  -> StateDelta + InferenceResult
```

This is the same pipeline described in the [README](../../README.md) and
frozen, layer by layer, in [COMPATIBILITY.md](../../COMPATIBILITY.md). Each
arrow is a versioned interface with its own conformance suite under
`conformance/`.

## Subsystems

| Subsystem | What it does | Docs |
| --- | --- | --- |
| **Compiler** | Python frontend: lexes/parses `.rsn` source, builds the Surface AST, lowers it to the canonical Semantic AST, then to Reason IR | [compiler.md](compiler.md) |
| **Runtime** | Rust execution engines that take Reason IR / an ExecutionPlan and produce committed `State` via a Prepare -> Validate -> Commit transaction protocol | [runtime.md](runtime.md) |
| **ReasonUnit** | The core typed, vector-valued graph node (`Concept`, `Object`, `Event`, `Action`, `Attribute`, `Goal`, `Constraint`) that both runtimes operate on | [reasonunit.md](reasonunit.md) |
| **ReasonUnit Object** | Scene/geometry composition built from ReasonUnit graphs (2D/3D projection) | [reasonunit-object.md](reasonunit-object.md) |
| **WorldModel** | Python SDK (`sdk/world`) for building, querying, and simulating spatial/semantic scenes on top of the runtime | [worldmodel.md](worldmodel.md) |
| **Cluster Runtime** | Not implemented — distributed execution is out of scope for the current alpha | [cluster-runtime.md](cluster-runtime.md) |
| **Tensor (IR)** | The numerical lowering stage inside RuntimeReal that executes graphs as matrix operations | [tensor.md](tensor.md) |

Two more subsystems sit around this core but are not detailed as separate
architecture pages yet — see the linked review reports for their state:

- **Toolchain** (`toolchain/`, the `reason` CLI) — see
  [docs/references/cli.md](../references/cli.md) and
  `docs/platform_architecture_review/toolchain_review.md`.
- **SDK / LSP / IDE** (`sdk/`, `frontend/lsp/`, `frontend/ide/`,
  `vscode-extension/`, `apps/reasonscript-ide/`) — see
  `docs/platform_architecture_review/sdk_review.md`,
  `lsp_review.md`, and `ide_review.md`.

## Two Complementary Semantic Layers

ReasonScript's specifications describe execution from two angles that both
apply to the same runtime state:

- **Operational Semantics** (imperative): `Goal`, `State`, `Transition`,
  `Constraint`, `Context`, `ExecutionPlan`, `StateDelta`, `InferenceResult` —
  "how execution runs." Normative spec:
  [docs/specifications/ReasonScript_Operational_Semantics_v0.1.md](../specifications/ReasonScript_Operational_Semantics_v0.1.md).
- **Semantic Language Core** (declarative): `SemanticUnit`,
  `SemanticRelation`, Reasoning Space, `SemanticPlan`, `SemanticSimulation`,
  `Knowledge` — "what reasoning means." Normative spec:
  [docs/specifications/ReasonScript_Semantic_Language_Core_v0.2.md](../specifications/ReasonScript_Semantic_Language_Core_v0.2.md).

The two are connected by a fixed mapping: `SemanticUnit -> State`,
`SemanticUnitType -> StateType`, `SemanticRelation -> Edge::relation`. Even
mathematical computation (algebra, calculus, linear algebra) is not a
special case — it is represented purely as `State --Transition--> State`
chains under the same rules
([ReasonScript_Computation_Model_v0.1.md](../specifications/ReasonScript_Computation_Model_v0.1.md)).

## Design Invariants

These hold across every subsystem above (see OS-01..OS-10 in the
Operational Semantics spec for the formal statement):

- **Determinism** — identical Reason IR + policies always produce the same
  `ExecutionPlan` and the same `InferenceResult`.
- **Commit-only mutation** — state changes only through a validated
  `StateDelta`; nothing mutates state directly.
- **Immutability once created** — an `ExecutionPlan`, once produced, does
  not change; rollback is a *new*, traced reverse delta, not an edit.
- **Auditability** — every commit is traceable back through its `Transition`
  and `Trace` to the `Goal` and `Constraint`s that justified it.

## Where Things Live in the Repository

```text
frontend/          Compiler frontend (Python): language_surface/, ast/, compiler/, lsp/, ide/
HybridRuntime/      Rust runtime crate: ambiguity resolution, semantic engines (SP1-SP9), ReasonGraph
RuntimeReal/        Rust runtime crate: the primary state-first execution engine, Tensor IR
RuntimeComplex/      Rust crate: early-stage stub reserved for a future runtime variant
sdk/                Python SDK: world/, reason_graph/, execution_plan/, agent/, planning/, runtime/
toolchain/          Python CLI implementation behind the `reason` command
schemas/            Versioned JSON Schemas (e.g. reason_ir.schema.json)
dto/                Common DTO bindings: Rust, Python, TypeScript, Go, Java
conformance/         Layered conformance framework and certification
docs/specifications/ Normative specs and validation reports for every frozen interface
```

## Next Steps

- New to the codebase: read [compiler.md](compiler.md) then
  [runtime.md](runtime.md) in order — they follow the pipeline above.
- Evaluating for a specific use case: read [worldmodel.md](worldmodel.md)
  for spatial/scene modeling, or [reasonunit.md](reasonunit.md) for the
  core graph model.
- Planning a contribution to a frozen interface: read
  [COMPATIBILITY.md](../../COMPATIBILITY.md) and
  [CONTRIBUTING.md](../../CONTRIBUTING.md) first.
