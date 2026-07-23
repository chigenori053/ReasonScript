# ReasonScript Core Concepts

Audience: engineers who need a working mental model of ReasonScript before
reading the normative specifications in `docs/`. This document assumes
professional software engineering background; it does not re-explain general
concepts such as ASTs, compilers, or graph theory.

For hands-on syntax and tooling, see `docs/guide/basic-usage.en.md`. This
document explains *why* the language is shaped the way it is.

## 1. What ReasonScript Is

ReasonScript is a reasoning-first language for building **proofable AI
workflows**: systems where a state transition — a decision, a plan step, a
calculation — can be produced deterministically and later audited from
recorded evidence, without re-running the world.

It is not a general-purpose programming language, not a knowledge base, and
not a natural-language reasoning system. It is a **language for representing
and executing reasoning as deterministic state transitions**, with every
transition traceable to the inputs and evidence that produced it.

The project ships as two coupled layers that are easy to conflate but serve
different purposes:

| Layer | Question it answers | Frozen specification |
|---|---|---|
| **Language Surface** | How do I write and compile a `.rsn` program? | `docs/ReasonScript_Language_Surface_Core_v0.1_RC.md` |
| **Semantic Language** | What does it mean to reason over typed semantic states? | `docs/ReasonScript_Semantic_Language_Core_v0.2.md` |

The Language Surface is the concrete syntax (`module`, `fn`, `calculation`,
`transition`, ...) described in `docs/guide/basic-usage.en.md`. The Semantic
Language is the abstract model underneath it — SemanticUnits, SemanticRelations,
Reasoning Spaces, and Knowledge — described in this document. A `.rsn` program
compiles down through both: source becomes Surface AST, Surface AST becomes a
Semantic AST that instantiates SemanticUnits and SemanticRelations, and that
Semantic AST lowers into the pipeline below.

## 2. Core Principles

Four principles govern every layer of the system, from the Language Surface
down to the Runtime. They are not stylistic preferences; they are the
properties the whole platform is validated against.

1. **Knowledge is not primitive. Knowledge is generated.** You never assert
   Knowledge directly. It only comes out of a validated simulation over a
   Reasoning Space, carrying the evidence that produced it.
2. **Reasoning precedes Knowledge.** There is no shortcut from raw data to a
   Knowledge object. A SemanticPlan must be simulated first.
3. **Every Knowledge object contains complete evidence.** A Knowledge value is
   self-auditing: the plan, the trace, and the confidence that produced it are
   preserved alongside it, so nothing needs to be re-derived to check it.
4. **Semantic reasoning is deterministic.** Given the same graph, the same
   plan, and the same constraints, the runtime always produces structurally
   equal results and byte-identical canonical JSON.

Determinism is the property that makes "proofable" meaningful: if execution
were allowed to vary between runs, evidence attached to a Knowledge object
would prove nothing about future runs.

## 3. The Reasoning Pipeline

The Semantic Language Core defines one directional pipeline that every
reasoning operation flows through:

```text
SemanticUnit
  -> SemanticRelation
  -> Reasoning Space
  -> SemanticPlan
  -> SemanticSimulation
  -> SimulationResult
  -> Knowledge
```

### SemanticUnit

The atomic, typed element of reasoning. The frozen types are `Concept`,
`Object`, `Event`, `Action`, `Attribute`, `Goal`, and `Constraint`. At runtime a
SemanticUnit is represented as a `State` (`StateType` is its runtime-level
type tag). There is no untyped or "unknown" SemanticUnit — `StateType::Unknown`
is explicitly invalid.

### SemanticRelation

A typed, directed connection between two SemanticUnits: `IsA`, `PartOf`,
`Cause`, `Similar`, `Constraint`, `Temporal`, `Spatial`, `Dependency`. At
runtime a SemanticRelation is an `Edge`. Relations are not free-form strings —
only the frozen set is structurally valid, and endpoint compatibility is
checked (see SCV-1 below).

### Reasoning Space

```text
Reasoning Space = SemanticUnits + SemanticRelations + SemanticConstraints + SemanticTransitions
```

A validated, private graph (`ReasonGraph`) that SemanticUnits and
SemanticRelations live in. It is deliberately **not** a knowledge base,
database, or persistent memory store — it exists to be reasoned over, not
queried like a repository. Reads borrow it immutably; any operation that
would hand back ownership consumes it, so there is no way to accidentally
mutate a Reasoning Space out from under an in-flight simulation.

### SCV-1: Structural Constraint Validation

Before anything enters the Reasoning Space, SCV-1 validates relation
compatibility, node references, state references/types, graph structure, and
closure-generated relations. This is the gate that keeps invalid semantic
topology (e.g. a `Cause` edge between two types that cannot causally relate)
out of the pipeline entirely — validation happens at construction time, not as
a runtime assertion deep in simulation.

### SemanticPlan

An external request: "reason from `start` toward `goal`", with optional
constraints (avoided nodes, maximum distance). A SemanticPlan is a request
object, not part of the Reasoning Space's own state — it does not get stored
in the graph.

### SemanticSimulation

The deterministic evaluator. Frozen operations are `simulate`,
`simulate_goal`, `simulate_goal_with_constraints`, and `predict`. Guarantees:
SCV-1 stays enforced during simulation, the Reasoning Space is never mutated,
equal inputs produce equal outputs, and the result is fully serializable.

### SimulationResult

A validated, structured trajectory:

```text
SimulationResult
├─ source_plan
├─ success
├─ path
├─ distance
├─ cost        = sum(edge costs)
├─ confidence  = product(edge confidences)
├─ trace       (relation, transition, cost, confidence, source/target types per step)
└─ predicted_states
```

Aggregated `cost`/`confidence` are normalized to 12 decimal places so JSON
round-trips reproduce byte-for-byte.

### Knowledge

```text
Knowledge = Validated Structured Reasoning Result
          = relation + evidence + confidence
```

Knowledge is never a raw fact, a raw relation, or a database row — it is what
falls out of a homogeneous, closure-compatible SimulationResult trajectory.
KEV-1 (Knowledge Emergence Validation) currently limits this to trajectories
built purely from `IsA`, `PartOf`, and `Cause` relations. Every Knowledge
object retains its source SemanticPlan, the complete SimulationResult, the
complete trace, and the validated confidence — it is auditable without
touching mutable graph state or any persistent store.

## 4. The Compilation Pipeline

Orthogonal to the reasoning pipeline above, there is a second pipeline that
takes ReasonScript **source code** down to something a Runtime can execute:

```text
Source Code
  -> Surface AST        (Language Surface Parser)
  -> Semantic AST        (declarations resolved, types checked)
  -> Reason IR           (versioned, schema-validated intermediate representation)
  -> ExecutionPlan       (immutable, ready for a Runtime)
  -> Runtime             (RuntimeReal / HybridRuntime)
  -> InferenceResult
```

Surface AST is where `module`, `fn`, `calculation`, `transition`, and
expression/pattern syntax live (see `docs/guide/basic-usage.en.md`). Compiling
a `calculation` or `transition` projects its statements onto the Semantic
Language vocabulary from Section 3 — for example, a `calculation`'s
`if`/`match` becomes a `DecisionTransition`, and its `result` statement becomes
a `ResultTransition` toward the calculation's semantic Goal. This is the seam
between "the syntax you write" and "the SemanticUnit/SemanticRelation graph
that gets reasoned over."

Reason IR is a stable, versioned schema (`schemas/reason_ir.schema.json`) —
it is the wire contract that lets independent Runtimes, the compiler, and
conformance tooling agree on meaning without sharing implementation code.
`Common_DTO_Specification_v0.1.md` defines matching data transfer objects for
Rust, Python, TypeScript, Go, and Java, so a Reason IR document produced by one
implementation is consumable by tooling in another language.

Two runtimes currently implement this contract: `RuntimeReal` (the reference
Rust runtime backing the Semantic Language v0.2 Core) and `HybridRuntime`
(adds ambiguity handling, planning, and closure/simulation extensions used by
later reasoning features). Both must reproduce identical InferenceResults for
identical ExecutionPlans — that is what "Runtime" means as an interchangeable
term in this codebase, not a single fixed binary.

## 5. State, Goals, Transitions, and Rollback

Operational Semantics v0.1 defines the execution meaning of a compiled
module. The execution configuration is:

```text
C = <M, IR, P, EP, S, D, T>
  M  source Module     IR reasonScript Reason IR   P  planner policy
  EP ExecutionPlan      S  committed State           D  StateDelta sequence
  T  execution trace
```

Execution advances only through a single **commit** relation:
`<EP, S_i, D, T> --commit(step_i)--> <EP, S_i+1, D+delta_i, T+event_i>`.
Planning and validation never mutate committed State — only a commit does,
and every commit is atomic and produces exactly one `StateDelta`
(`before_state` -> `after_state`).

A **Goal** is an immutable terminal satisfaction condition, not a plan step
and not a mutation. `reach_state` satisfaction is purely structural:
`S.state_id == target`. Every execution has exactly one Goal; a zero-step
execution is valid if the initial State already satisfies it.

A **Transition** is a planner-selectable declaration of a possible state
change — the runtime counterpart of the `transition { ... }` construct you
write in source, and also the target that every `calculation` statement
projects to (`StateUpdateTransition`, `CallTransition`, `DecisionTransition`,
`ResultTransition`, ...).

**Rollback** reverts committed State to a previously recorded safe
checkpoint. In the original core primitive model (`docs/semantics.md`),
`rollback` is a first-class statement, and `prove` failures containing the
literal marker `invalid` trigger it automatically — this is what makes the
platform "rollback-safe": a failed proof cannot leave the system in a
half-applied state.

## 6. What ReasonScript Deliberately Is Not

The v0.2 Core freeze is explicit about scope, and it is worth internalizing
these boundaries because they are easy to assume by analogy with adjacent
systems:

- Not a Knowledge Repository, persistence layer, or retrieval system —
  Knowledge is produced per-simulation, not stored and queried later.
- No Knowledge re-reasoning — you don't reason *about* a Knowledge object
  through the same pipeline; you re-run a SemanticPlan.
- No MemorySpace or WorldModel semantics at the Core level (WorldModel exists
  as a separate, higher SDK layer — see `docs/World_SDK_Phase_1_Specification.md`).
- No natural language parsing — SemanticUnits are constructed programmatically
  or via the Language Surface, never inferred from prose.
- No external execution and no claim of real-world truth — a validated
  SimulationResult is internally consistent and reproducible, not a claim that
  it matches reality.
- SCV-2 through SCV-5 (temporal, causal, spatial, dependency constraint
  validation beyond SCV-1's structural checks) are reserved for future
  specifications, not implemented in the v0.2 Core.

## 7. Determinism as an Engineering Constraint

Every layer's test suite and release gate exists to defend the same
guarantee: identical input produces identical output. Concretely, this shows
up as:

- Canonical JSON serialization with fixed decimal normalization (12 places for
  simulation metrics) so that `deserialize(serialize(x)) == x` and repeated
  runs are byte-comparable.
- Immutable AST, IR, and ExecutionPlan values — every node is immutable once
  constructed, and containers are ordered tuples, not sets, so source order is
  preserved end-to-end.
- Structural equality (not identity equality) as the basis for State snapshot
  comparison, so two independently computed snapshots with the same content
  are recognized as equal.
- Release gates (`release/*/run_release_validation.py`) that re-run the full
  chain from source to InferenceResult and fail the build on any deviation.

When you extend the language or runtime, the operative question is not "does
this feature work" but "does this feature preserve determinism and evidence
end to end" — that is the bar every accepted specification in `docs/` was
held to.

## 8. Where to Go Next

- For concrete syntax, the toolchain, and how to write and run a `.rsn`
  program: `docs/guide/basic-usage.en.md`.
- For the exact grammar: `docs/grammar.md` (original line-based core) and
  `docs/ReasonScript_Language_Surface_Core_v0.1_RC.md` (current block-structured
  surface).
- For the full Semantic Language Core contract:
  `docs/ReasonScript_Semantic_Language_Core_v0.2.md`.
- For execution semantics: `docs/ReasonScript_Operational_Semantics_v0.1.md`.
- For the platform's overall maturity and what remains before Beta:
  `docs/platform_architecture_review/platform_architecture_v1.md`.
