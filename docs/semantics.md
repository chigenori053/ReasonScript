# ReasonScript Core Semantics

## Purpose
ReasonScript is a reasoning-first language for AI systems,
proofable workflows, deterministic execution,
and rollback-safe state transitions.

## Core primitives
- goal: declare desired state
- derive: generate candidate reasoning
- prove: validate derivation
- apply: commit verified change
- converge: stabilize state
- rollback: revert to prior safe state

## Type lattice v0

Each primitive carries a typed payload:

| Primitive  | Type   | Semantics                                      |
|------------|--------|------------------------------------------------|
| `goal`     | Symbol | goal identifier                                |
| `derive`   | Symbol | reasoning strategy label                       |
| `converge` | Symbol | stabilization label                            |
| `rollback` | State  | safe checkpoint to restore                     |
| `apply`    | State  | committed runtime state value                  |
| `prove`    | Proof  | invariant symbol; `invalid` triggers auto-rollback |

### Symbol
Names goals, strategies, and convergence labels. Does not mutate state.

### State
Represents committed execution state. `apply` writes it; `rollback` restores it.

### Proof
Carries an invariant symbol. Any `Proof` whose inner string contains `invalid`
is treated as a deterministic proof failure and triggers automatic rollback to
the last safe `State` checkpoint.
