# ReasonScript Semantic Language v0.2

## Reasoning Space Specification v0.1-draft

### Document Information

- Specification: Reasoning Space
- Version: 0.1-draft
- Target: ReasonScript Semantic Language v0.2
- Status: Draft implementation
- Prerequisites:
  - SemanticUnit
  - SemanticRelation
  - SCV-1 Structural Constraint Validation

## Purpose

A Reasoning Space is the validated semantic environment in which structured
reasoning is performed.

A Reasoning Space is not a knowledge base, persistent memory system, or
knowledge repository. It contains semantic units, relations, constraints, and
transitions that may be operated on by a reasoning process.

Knowledge is treated as a validated result of reasoning rather than a primitive
stored by the Reasoning Space API.

## Formal Model

```text
Reasoning Space
=
Semantic Units
+
Semantic Relations
+
Semantic Constraints
+
Semantic Transitions
```

In `RuntimeReal`, the canonical graph representation is:

```text
ReasoningSpace
    |
    +-- ReasonGraph
          +-- State      (SemanticUnit)
          +-- Node       (SemanticUnit reference)
          +-- Edge       (SemanticRelation + SemanticTransition)
```

Only `GraphType::ReasonGraph` can be promoted to a `ReasoningSpace`.
`KnowledgeGraph`, `MemoryGraph`, `WorldGraph`, and `PlanningGraph` are rejected.
This enforces the distinction between a reasoning environment and storage or
plan representations.

## Runtime Mapping

| Semantic Language | RuntimeReal |
| --- | --- |
| Reasoning Space | `ReasoningSpace` over `ReasonGraph` |
| SemanticGraph | `ReasonGraph` |
| SemanticUnit | `State` |
| SemanticUnitType | `StateType` |
| SemanticUnit reference | `Node` |
| SemanticRelation | `Edge::relation` |
| SemanticTransition | `Edge::transition` |
| StructuralConstraint | `StructuralConstraintValidator` |
| SemanticPlan request | `SemanticPlan` |
| Reasoning path | `ReasoningPath` |
| Graph IR | `GraphIR` |

## Components

### SemanticUnit

`State` is the current semantic unit representation. Every graph node references
a state. SCV-1 validates the supported semantic unit types.

### SemanticRelation

`RelationType` currently supports:

- `IsA`
- `PartOf`
- `Cause`
- `Similar`
- `Constraint`
- `Temporal`
- `Spatial`
- `Dependency`

`Custom(...)` is not implemented in `RuntimeReal` v0.1 because
`RelationType` is a closed enum.

### SemanticConstraint

SCV-1 is mandatory when constructing or operating a Reasoning Space.
Contextual semantic validation is applied by `SemanticValidator`.

Temporal, causal-truth, spatial, and dependency-specific validators remain
outside this draft.

### SemanticTransition

Each edge carries a `Transition`. The supported transition kinds are:

- `Deduction`
- `Induction`
- `Abduction`
- `Search`
- `Simulation`
- `Optimization`

## Invariants

1. The backing graph has `GraphType::ReasonGraph`.
2. The backing graph passes SCV-1 before it enters a Reasoning Space.
3. The backing graph is exposed read-only through `ReasoningSpace::graph`.
4. Exploration and planning validate graph structure before use.
5. Closure validates the space before and after inference.
6. Closure does not generate a relation that violates the SCV-1 matrix.

## Operations

### Validation

```rust
space.validate(&semantic_context)
```

Runs structural validation and current contextual semantic validation.

### Exploration

```rust
space.explore(start_node)
```

Returns all nodes reachable through directed semantic relations in
deterministic breadth-first order.

### Closure

```rust
space.close(&semantic_context)
```

Generates valid transitive `IsA`, `PartOf`, and `Cause` relations until a fixed
point is reached. Every candidate inferred relation is checked against SCV-1.

Example:

```text
Dog IsA Mammal
Mammal IsA Animal

=> Dog IsA Animal
```

### Planning

`SemanticPlan` is an external request containing a start node and goal node.
It is not stored in the Reasoning Space.

```rust
space.execute_plan(&SemanticPlan::new(start, goal))
```

The result is a shortest directed `ReasoningPath`. Executing a plan request
does not mutate the Reasoning Space.

### Graph IR

```rust
space.to_graph_ir()
```

Produces the current serializable graph representation for lowering or
transport.

## Knowledge Emergence

The runtime implements the following part of the proposed pipeline:

```text
Reasoning Space
    |
    +-- SemanticPlan request
    |
    +-- validated ReasoningPath
    |
    +-- closure-generated relations
```

Closure-generated relations remain graph relations. KEV-1 now provides the
separate validated promotion boundary:

```text
SimulationResult -> Knowledge
```

This creates an explicit traceable Knowledge value. It does not persist the
value or turn the Reasoning Space into a knowledge repository.

## Non-Goals

- Persistent memory
- Database storage
- Knowledge repositories
- Natural language parsing
- World simulation physics
- Truth verification of inferred relations

## Adoption Criteria

The draft is eligible for formal adoption when:

1. SemanticUnit and SemanticRelation representations are adopted.
2. SCV-1 is adopted.
3. SemanticGraph representation and Graph IR round trips are validated.
4. SemanticPlan requests are validated against a Reasoning Space.
5. The remaining `Custom(...)` relation and simulation-result requirements are
   either implemented or explicitly deferred by the v0.2 language scope.
