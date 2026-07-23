# ReasonUnit

`ReasonUnit` is the concrete data structure at the heart of both runtimes: an
identified, typed, vector-valued graph node. `SemanticUnit` is the related
*specification*-level concept it implements. This page covers both, since
in practice every `State`/`ReasonUnit` in the runtime is expected to carry a
`SemanticUnit` type.

## The `ReasonUnit` Struct

Defined in `RuntimeReal/src/core/reason_unit.rs`:

```rust
pub struct ReasonUnit {
    id: Uuid,
    label: String,
    unit_type: UnitType,       // RuntimeReal/src/core/types.rs
    vector: Array1<f64>,
    metrics: ReasonUnitMetrics,           // activation/closure/propagation counters
    identity_metrics: Option<IdentityMetrics>,
}
```

It supports vector algebra (`add`, `sub`, `neg`) directly, because
transitions between `ReasonUnit`s are often expressed as vector operations
(see [tensor.md](tensor.md) for how a graph of these is lowered to matrix
form for execution).

`HybridRuntime` uses a related but distinct wrapper, `HybridReasonUnit`
(`HybridRuntime/src/state.rs`), as the type its `HybridRuntime::new(...)`
API operates on — see [runtime.md](runtime.md#hybridruntime) for how it's
used in ambiguity resolution.

## SemanticUnit: The Seven Frozen Types

`SemanticUnit` is the specification-level classification every `ReasonUnit`
is expected to carry (`StateType::Unknown` is explicitly disallowed). It is
defined in
[ReasonScript_Semantic_Language_Core_v0.2.md](../specifications/ReasonScript_Semantic_Language_Core_v0.2.md)
as: "Fundamental reasoning-typed semantic element." The **seven frozen
SemanticUnit types**, adopted in the v0.2 Core freeze
(see [CHANGELOG.md](../../CHANGELOG.md)), are:

| Type | Meaning |
| --- | --- |
| `Concept` | An abstract category or idea |
| `Object` | A concrete entity |
| `Event` | Something that occurs at a point/interval |
| `Action` | An agent-driven operation |
| `Attribute` | A property attached to another unit |
| `Goal` | A desired terminal condition |
| `Constraint` | A side-effect-free predicate over state |

These same seven names are also the "Reason State" type category in the
language's type system (`StateTypeNode`) — see
[docs/language/type-system.md](../language/type-system.md). The runtime
mapping is direct: `SemanticUnit -> State`, `SemanticUnitType -> StateType`.
In code this surfaces as `SemanticUnitType`
(`RuntimeReal/src/core/structural_constraint.rs`) and
`SemanticType`/`SemanticTypeId`/`SemanticTypeRegistry`
(`HybridRuntime/src/semantic_type.rs`).

## SemanticRelation: The Eight Frozen Relations

Edges between `ReasonUnit`s are typed by `SemanticRelation`, mapped to
`Edge::relation`:

| Relation | Meaning |
| --- | --- |
| `IsA` | Subtype/instance-of |
| `PartOf` | Compositional membership |
| `Cause` | Causal link |
| `Similar` | Similarity |
| `Constraint` | Constraining relationship |
| `Temporal` | Time-ordered relationship |
| `Spatial` | Spatial relationship |
| `Dependency` | Depends-on relationship |

Knowledge emergence (KEV-1) is currently limited to `IsA`, `PartOf`, and
`Cause` trajectories — see
[ReasonScript_Semantic_Language_Core_v0.2.md](../specifications/ReasonScript_Semantic_Language_Core_v0.2.md)
and the KEV-1 specs under `docs/specifications/`.

## Why Two Layers (ReasonUnit vs. SemanticUnit)?

`ReasonUnit` is what actually exists at runtime: a struct with a UUID, a
vector, and mutation counters. `SemanticUnit` is the contract that
constrains what a *valid* `ReasonUnit` graph looks like: every node must be
one of the seven types, every edge one of the eight relations, and SCV-1
structural validation enforces this before a graph can be reasoned over.
This separation lets the runtime evolve its internal representation
(vectors, metrics, storage) independently from the semantic contract that
tooling, SDKs, and specs are written against.

## Where to Go Next

- [reasonunit-object.md](reasonunit-object.md) — composing `ReasonUnit`
  graphs into 2D/3D scenes.
- [worldmodel.md](worldmodel.md) — the higher-level SDK built on top of
  this graph model.
- [docs/language/type-system.md](../language/type-system.md) — how these
  seven types surface in `.rsn` source as `StateTypeNode` annotations.
