# Glossary

Terms are cross-referenced to the page that defines them normatively.

**Calculation** — A block (`calculation Name { ... }`) that computes a named
result, typically by calling functions. See
[docs/language/syntax.md](../language/syntax.md#calculations).

**Constraint** — One of the six core language concepts and one of the seven
frozen `SemanticUnit` types: a side-effect-free predicate that may reject a
candidate `Transition` but never mutates state. See
[docs/language/semantics.md](../language/semantics.md#core-concepts).

**Context** — An optional, external, non-owned typed reference available to
a module; read-only, never execution-affecting on its own. See
[docs/language/semantics.md](../language/semantics.md#core-concepts).

**ExecutionPlan** — The immutable, deterministic plan produced by the
planner from a Reason IR planning request; once created, it does not
change. See [docs/architecture/compiler.md](../architecture/compiler.md#from-reason-ir-to-executionplan).

**Goal** — One of the six core language concepts and one of the seven
frozen `SemanticUnit` types: the desired terminal condition of a module.
Exactly one per module; immutable. See
[docs/language/semantics.md](../language/semantics.md#core-concepts).

**HybridReasonUnit** — The `ReasonUnit` wrapper type used specifically by
`HybridRuntime` (`HybridRuntime/src/state.rs`). See
[docs/architecture/runtime.md](../architecture/runtime.md#hybridruntime).

**HybridRuntime** — One of ReasonScript's three Rust runtime crates;
focuses on resolving ambiguous state via a cost-based `DecisionEngine`, and
hosts the Semantic Language v0.2 engines (SP1-SP9). See
[docs/architecture/runtime.md](../architecture/runtime.md#hybridruntime).

**InferenceResult** — The outcome of an execution: `completed`, `rejected`,
`decision_required`, or `failed`. See
[docs/language/semantics.md](../language/semantics.md#the-ten-operational-semantics-rules-os-01os-10).

**Knowledge** — The validated output of the Semantic Language v0.2
pipeline's final stage, produced under KEV-1 evidence rules. See
[ReasonScript_Semantic_Language_Core_v0.2.md](../specifications/ReasonScript_Semantic_Language_Core_v0.2.md).

**Reason IR** — The versioned (`reason-ir/0.1`), schema-validated JSON
intermediate representation produced by the Compiler and consumed by the
planner/runtime. See [docs/architecture/compiler.md](../architecture/compiler.md#3-reason-ir--frontendcompilercompilerpy).

**ReasonGraph** — The graph of `ReasonUnit`s and `SemanticRelation` edges
that `HybridRuntime` and `RuntimeReal` operate on. See
[docs/architecture/reasonunit.md](../architecture/reasonunit.md).

**Reasoning Space** — The immutable-during-simulation space in which a
`SemanticPlan` is evaluated, part of the Semantic Language v0.2 pipeline.
See `RuntimeReal/src/graph/reasoning_space.rs` and
[ReasonScript_Semantic_Language_Core_v0.2.md](../specifications/ReasonScript_Semantic_Language_Core_v0.2.md).

**ReasonUnit** — The core runtime data structure: an identified, typed,
vector-valued graph node (`RuntimeReal/src/core/reason_unit.rs`). See
[docs/architecture/reasonunit.md](../architecture/reasonunit.md).

**ReasonUnit Object** — Not a formally specified type; informal shorthand
for the `ru_obj` test pattern that projects a `ReasonUnit` graph into a
renderable 2D/3D scene. See
[docs/architecture/reasonunit-object.md](../architecture/reasonunit-object.md).

**RuntimeComplex** — A Rust crate reserved for a future complex-valued
runtime variant; currently a stub with no real behavior. See
[docs/architecture/runtime.md](../architecture/runtime.md#runtimecomplex).

**RuntimeReal** — The primary, production-path Rust execution engine,
implementing the Prepare -> Validate -> Commit -> StateDelta transaction
protocol. See [docs/architecture/runtime.md](../architecture/runtime.md#runtimereal).

**SemanticPlan** — A plan expressed in Semantic Language Core terms
(declarative), evaluated within a Reasoning Space to produce a
`SemanticSimulation`. See
[ReasonScript_Semantic_Language_Core_v0.2.md](../specifications/ReasonScript_Semantic_Language_Core_v0.2.md).

**SemanticRelation** — One of eight frozen edge types between
`SemanticUnit`s: `IsA`, `PartOf`, `Cause`, `Similar`, `Constraint`,
`Temporal`, `Spatial`, `Dependency`. See
[docs/architecture/reasonunit.md](../architecture/reasonunit.md#semanticrelation-the-eight-frozen-relations).

**SemanticUnit** — One of seven frozen node types: `Concept`, `Object`,
`Event`, `Action`, `Attribute`, `Goal`, `Constraint`. Maps 1:1 to `State` /
`StateType` at the runtime level, and to `StateTypeNode` in the type
system. See
[docs/architecture/reasonunit.md](../architecture/reasonunit.md#semanticunit-the-seven-frozen-types).

**State** — One of the six core language concepts: an owned, serializable
snapshot; exactly one initial `State` per module; mutated only via a
committed `StateDelta`. See
[docs/language/semantics.md](../language/semantics.md#core-concepts).

**StateDelta** — An append-only record of a state mutation; rollback is
expressed as a new reverse `StateDelta`, never an edit to history. See
[docs/language/semantics.md](../language/semantics.md#the-ten-operational-semantics-rules-os-01os-10).

**Tensor IR** — The internal numerical IR (`TensorIR`, `TensorOp`) that
`RuntimeReal` lowers `ReasonGraph`s into for matrix-based execution. Not a
standalone product. See [docs/architecture/tensor.md](../architecture/tensor.md).

**Transition** — One of the six core language concepts: a candidate
source-to-target move with identity, cost, guard, and effect; not
inherently deterministic on its own — the planner resolves ambiguity. See
[docs/language/semantics.md](../language/semantics.md#core-concepts).

**WorldModel / World SDK** — The Python SDK (`sdk/world/`) for building,
querying, validating, and simulating spatial/semantic scenes: core,
spatial, semantic, and simulation layers. See
[docs/architecture/worldmodel.md](../architecture/worldmodel.md).

## Not (Yet) ReasonScript Terms

These are sometimes assumed to exist but currently don't — see the linked
pages for what exists instead:

- **Cluster Runtime** — not implemented. See
  [docs/architecture/cluster-runtime.md](../architecture/cluster-runtime.md).
- **Standard library** — does not exist. See
  [docs/language/standard-library.md](../language/standard-library.md).
