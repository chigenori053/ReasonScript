# Semantics

This page describes what a `.rsn` program *means* when it runs — the
execution model behind the syntax in [syntax.md](syntax.md). For the
implementation that realizes this model, see
[docs/architecture/compiler.md](../architecture/compiler.md) and
[docs/architecture/runtime.md](../architecture/runtime.md).

## Core Concepts

ReasonScript's execution model is built from six orthogonal concepts,
defined normatively in
[ReasonScript_Language_Specification_v0.1.md](../specifications/ReasonScript_Language_Specification_v0.1.md):

| Concept | Meaning | Mutates state? |
| --- | --- | --- |
| **Goal** | Desired terminal condition; exactly one per module | No |
| **State** | Owned, serializable snapshot; exactly one initial `State` per module | Only via an applied plan step + `StateDelta` |
| **Transition** | Candidate source -> target move: identity, source, relation, target, cost, guard, effect | Only when committed |
| **Constraint** | Side-effect-free predicate that may reject a candidate | Never |
| **Context** | External, non-owned typed reference (optional) | Never |
| **Metadata** | Optional JSON annotation | Never affects execution |

A `Transition` is not inherently deterministic on its own — when multiple
transitions are viable, the planner resolves the ambiguity (see
[Planning](#planning) below).

## Execution Model

```text
Module -> Semantic AST -> Reason IR planning request -> planner -> ExecutionPlan -> executor -> StateDelta(s) + InferenceResult
```

An `ExecutionPlan` is immutable once created — see
[docs/architecture/compiler.md](../architecture/compiler.md#from-reason-ir-to-executionplan).

## The Ten Operational Semantics Rules (OS-01..OS-10)

The normative execution semantics
([ReasonScript_Operational_Semantics_v0.1.md](../specifications/ReasonScript_Operational_Semantics_v0.1.md))
define a configuration `C = <M, IR, P, EP, S, D, T>` and a single
state-evolution rule, `commit(step_i)`. Ten rule groups govern it:

1. **Goal** — immutable for the life of the module.
2. **State** — identity-stable; mutated only by commit.
3. **Transition** — three sub-phases: `prepare` -> `validate` -> `commit`.
4. **Constraint** — purity is enforced; a constraint that attempts to
   mutate state is rejected at validation.
5. **Context** — read-only external references.
6. **Planning** — deterministic selection by minimum expected cost, with a
   full deterministic tie-break key: `(total cost, step count,
   transition_id sequence)`.
7. **ExecutionPlan** — immutable once produced.
8. **StateDelta** — append-only; rollback is expressed as a *reverse*
   delta, never an edit to history.
9. **InferenceResult** — one of `completed`, `rejected`,
   `decision_required`, `failed`.
10. **Runtime Correctness** — the invariants listed in
    [docs/architecture/overview.md](../architecture/overview.md#design-invariants):
    goal immutability, state identity stability, constraint purity, plan
    immutability, delta traceability, determinism, commit-only mutation,
    auditability.

## Pattern Matching Semantics

Match evaluation order (see
[pattern_guard_v1.md](../specifications/pattern_guard_v1.md) and
[match_semantic_integration_v1.md](../specifications/match_semantic_integration_v1.md)):

1. Try each arm's pattern against the scrutinee, top to bottom.
2. On a structural match, bind pattern variables in that arm's scope.
3. If the arm has a `when` guard, evaluate it with those bindings.
4. If the guard is false (or absent and the pattern didn't match), continue
   to the next arm.
5. Guarded arms do not count toward exhaustiveness checking — the compiler
   still requires an unguarded arm (or `default`) that can't fail.

Or-patterns (`A | B`) require every alternative to bind the same names with
compatible pattern categories, and reject duplicate alternatives — see
[or_pattern_v1.md](../specifications/or_pattern_v1.md).

## Computation Is Not a Special Case

All mathematical computation — algebra, calculus, linear algebra,
trigonometry, multivariable calculus, abstract math — is represented purely
as `State --Transition--> State` chains under the same OS-01..OS-10
contract. There is no separate math evaluator or commit path; a numeric
result is just data in `State.data`, produced by deterministic `effect`
functions on ordinary `Transition`s. See
[ReasonScript_Computation_Model_v0.1.md](../specifications/ReasonScript_Computation_Model_v0.1.md).

## Two Semantic Vocabularies, One Runtime

Everything above is the **Operational Semantics** (imperative) view. There
is a second, **Semantic Language Core** (declarative) vocabulary —
`SemanticUnit`, `SemanticRelation`, Reasoning Space, `SemanticPlan`,
`SemanticSimulation`, `Knowledge` — that describes the same runtime state
from a reasoning/knowledge-graph angle. See
[docs/architecture/reasonunit.md](../architecture/reasonunit.md) for how
the two connect (`SemanticUnit -> State`, `SemanticRelation ->
Edge::relation`).

## Rollback and Proof Failure

A `Proof` (in the legacy core grammar, see
[syntax.md](syntax.md#legacy-core-grammar-historical)) carries an invariant
symbol; a proof whose content is invalid is a deterministic failure that
triggers automatic rollback to the last safe `State` checkpoint — rollback
is always a traced reverse delta, never a silent revert. This is the
runtime behavior [SECURITY.md](../../SECURITY.md) and
[COMPATIBILITY.md](../../COMPATIBILITY.md) refer to when they describe
ReasonScript's auditability guarantees.
