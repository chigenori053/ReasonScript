# ReasonScript Semantic Language v0.2 Core Specification

## Document Information

- Specification: ReasonScript Semantic Language Core
- Version: `reasonscript-semantic-language/0.2`
- Status: CORE FROZEN
- Freeze date: 2026-06-15
- Release type: Semantic Language Foundation
- Runtime mapping: `RuntimeReal`
- Prerequisites:
  - RuntimeReal
  - SCV-1
  - Reasoning Space
  - SSV-1
  - KEV-1

## 1. Purpose

ReasonScript Semantic Language v0.2 defines a deterministic semantic
state-transition model for structured reasoning.

Its core responsibilities are:

- representation of semantic states;
- representation of semantic relations;
- construction of validated Reasoning Spaces;
- deterministic semantic simulation;
- validated Knowledge emergence.

The Semantic Language is not a knowledge representation language. It is a
semantic reasoning state-transition language.

## 2. Core Principles

1. Knowledge is not primitive. Knowledge is generated.
2. Reasoning precedes Knowledge.
3. Every Knowledge object contains complete evidence.
4. Semantic reasoning is deterministic.

Given the same graph, plan, and constraints, the runtime produces structurally
equal results and equal canonical JSON.

## 3. SemanticUnit

```text
SemanticUnit = Fundamental reasoning-typed semantic element
```

The frozen SemanticUnit types are:

- `Concept`
- `Object`
- `Event`
- `Action`
- `Attribute`
- `Goal`
- `Constraint`

Runtime mapping:

```text
SemanticUnit     -> State
SemanticUnitType -> StateType
```

`StateType::Unknown` is not a valid SemanticUnit type.

## 4. SemanticRelation

A SemanticRelation is a typed semantic connection between SemanticUnits.

The frozen core relations are:

- `IsA`
- `PartOf`
- `Cause`
- `Similar`
- `Constraint`
- `Temporal`
- `Spatial`
- `Dependency`

Runtime mapping:

```text
SemanticRelation -> Edge::relation
```

## 5. Structural Constraint System

SCV-1 status: **ADOPTED**

SCV-1 validates:

- relation compatibility;
- node references;
- state references and types;
- graph structure;
- closure-generated relations.

Invalid semantic topology cannot enter the validated reasoning pipeline.
Temporal, spatial, and dependency-specific semantics remain reserved for later
SCV specifications.

## 6. Reasoning Space

```text
Reasoning Space
= Semantic Units
+ Semantic Relations
+ Semantic Constraints
+ Semantic Transitions
```

A `ReasoningSpace` is a validated semantic state-transition environment backed
by a `ReasonGraph`.

It is not a Knowledge Base, persistent memory, database, or repository.

The graph is private to the domain object. Read operations borrow it
immutably; operations that return ownership consume the Reasoning Space.

## 7. SemanticPlan

A `SemanticPlan` is an external reasoning request executed against a Reasoning
Space.

It contains:

- `start`;
- `goal`;
- optional constraints:
  - avoided nodes;
  - maximum distance.

A SemanticPlan is not stored in the Reasoning Space.

## 8. SemanticSimulation

`SemanticSimulation` deterministically evaluates semantic trajectories.

Frozen operations:

- `simulate`;
- `simulate_goal`;
- `simulate_goal_with_constraints`;
- `predict`.

Guarantees:

- SCV-1 is enforced;
- the Reasoning Space is not mutated;
- equal inputs produce equal output;
- output is serializable and reproducible.

## 9. SimulationResult

A `SimulationResult` is a validated structured reasoning trajectory.

```text
SimulationResult
├─ source_plan
├─ success
├─ path
├─ distance
├─ cost
├─ confidence
├─ trace
└─ predicted_states
```

Metrics:

```text
cost       = sum(edge costs)
confidence = product(edge confidences)
```

Aggregated metrics are normalized to 12 decimal places for deterministic JSON
round trips. Every trace step records relation, transition, cost, confidence,
and source/target SemanticUnit types.

## 10. Knowledge

```text
Knowledge = Validated Structured Reasoning Result
```

Knowledge is not a raw relation, raw graph, or stored fact.

```text
Knowledge
├─ relation
├─ evidence
└─ confidence
```

KEV-1 emergence is limited to homogeneous, closure-compatible trajectories:

- `IsA`;
- `PartOf`;
- `Cause`.

## 11. Knowledge Evidence

Every Knowledge object preserves:

- the source SemanticPlan;
- the complete SimulationResult;
- the complete trace;
- the validated confidence.

Knowledge is auditable without consulting mutable graph state or persistent
storage.

## 12. Core Pipeline

```text
SemanticUnit
    |
SemanticRelation
    |
Reasoning Space
    |
SemanticPlan
    |
SemanticSimulation
    |
SimulationResult
    |
Knowledge
```

## 13. Runtime Guarantees

The v0.2 Core guarantees:

- deterministic path selection and result generation;
- SCV-1 enforcement at graph, simulation, and Knowledge boundaries;
- Reasoning Space immutability during simulation;
- trace preservation;
- evidence preservation;
- confidence preservation;
- JSON reproducibility.

These guarantees apply to identical serialized inputs and the same RuntimeReal
v0.2 Core implementation.

## 14. Explicitly Out of Scope

- SCV-2 Temporal Constraint
- SCV-3 Causal Constraint
- SCV-4 Spatial Constraint
- SCV-5 Dependency Constraint
- Knowledge Repository
- Knowledge Persistence
- Knowledge Retrieval
- Knowledge Re-Reasoning
- MemorySpace
- WorldModel
- Natural Language Parsing
- External Execution
- truth or real-world correctness

## 15. Core Freeze Declaration

The following concepts are frozen as ReasonScript Semantic Language v0.2 Core:

- SemanticUnit
- SemanticRelation
- SCV-1
- Reasoning Space
- SemanticPlan
- SemanticSimulation
- SimulationResult
- Knowledge

Future specifications may extend this foundation but must not violate its
determinism, validation boundaries, evidence model, or Knowledge definition.

ReasonScript Semantic Language v0.2 is therefore defined as:

```text
A Deterministic Semantic State Transition Language
with Validated Knowledge Emergence
```
