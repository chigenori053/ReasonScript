# Reasoning Space Validation Report v0.1-draft

## Summary

- Date: 2026-06-15
- Target: ReasonScript Semantic Language v0.2
- Runtime: `RuntimeReal`
- Result: PASS for the implemented draft scope
- Formal adoption recommendation: Conditional

## Implementation

### ReasoningSpace domain type

Added `graph::reasoning_space` with:

- `ReasoningSpace`
- `ReasoningSpaceError`
- `SemanticPlan`
- `ReasoningPath`
- `ExplorationResult`
- `ClosureResult`

`ReasoningSpace` owns a private `ReasonGraph`. It exposes read-only graph access
and consumes itself when returning an owned graph. This prevents callers from
bypassing validation through ordinary mutable access.

### Graph identity

Construction accepts only `GraphType::ReasonGraph`. A `KnowledgeGraph` cannot
be treated as a Reasoning Space, directly implementing the specification's
distinction:

```text
Reasoning Space != Knowledge Base
```

### SCV-1 integration

`ReasoningSpace::from_graph`, exploration, planning, and closure apply SCV-1.
Contextual validation is available through `ReasoningSpace::validate`.

### Closure correction

The existing closure engine could previously derive:

```text
Action Cause Event
Event Cause Attribute
=> Action Cause Attribute
```

The derived relation violates the SCV-1 matrix. Closure generation now checks
the inferred source and target types before adding an edge. The invalid
candidate is skipped while valid taxonomic, part-whole, and causal closure
remain supported.

### Reasoning operations

Implemented:

- Validation
- Directed breadth-first exploration
- Fixed-point closure
- Shortest-path SemanticPlan execution
- Graph IR conversion

All six existing transition kinds can be represented on Reasoning Space edges.

## Validation Cases

| ID | Validation | Result |
| --- | --- | --- |
| RS-001 | Valid SemanticGraph becomes a ReasoningSpace | PASS |
| RS-002 | SCV-invalid graph is rejected | PASS |
| RS-003 | KnowledgeGraph is rejected | PASS |
| RS-004 | Exploration finds reachable states | PASS |
| RS-005 | SemanticPlan returns the shortest path without mutation | PASS |
| RS-006 | Missing plan node returns a typed error | PASS |
| RS-007 | Existing but unreachable goal returns `GoalUnreachable` | PASS |
| RS-008 | Closure generates `Dog IsA Animal` | PASS |
| RS-009 | Closure suppresses SCV-invalid causal inference | PASS |
| RS-010 | GraphIR JSON round trip remains constructible | PASS |
| RS-011 | All transition kinds are representable | PASS |

The canonical test suite is:

```text
RuntimeReal/tests/reasoning_space_validation.rs
```

Dedicated Reasoning Space result: 11 passed, 0 failed.

Regression command:

```text
cargo test -- --skip vs2_scaling_benchmarks
```

Regression result:

- 65 tests passed
- 0 tests failed
- 1 pre-existing scaling benchmark filtered out
- Documentation tests passed

The excluded benchmark performs debug-mode transitive closure for 100, 500,
and 1000-node graphs and was already identified as unsuitable for the normal
regression path. The mixed semantic closure benchmark passed.

## Specification Assessment

### Purpose and definition

Validated. The runtime now has a domain type distinct from graph storage types,
with explicit semantic operations and structural invariants.

### SemanticGraph representation

Validated. `ReasonGraph` remains the canonical structural representation, and
`GraphIR` provides the serializable IR wrapper.

### Exploration and closure

Validated. Reachability and fixed-point relation inference are implemented.
Closure now preserves SCV-1.

### SemanticPlan relationship

Validated for deterministic shortest-path planning. `SemanticPlan` is passed
to the Reasoning Space and is not stored in it.

### Simulation

Partially validated. `TransitionType::Simulation` is representable, and the
existing runtime executor supports graph dynamics. A dedicated API that
evaluates alternative SemanticPlan trajectories and emits a validated
simulation result is not part of this draft implementation.

### Knowledge emergence

Partially validated. Closure produces validated inferred relations, but no
result is promoted into a persistent knowledge object or repository. This is
consistent with the non-goals, but the complete:

```text
SemanticPlan -> SemanticSimulation -> Validated Result -> Knowledge
```

pipeline remains future work.

## Adoption Criteria

| Criterion | Status |
| --- | --- |
| SemanticUnit adopted | Satisfied by current `State` mapping |
| SemanticRelation adopted | Satisfied for current closed `RelationType` |
| SCV-1 adopted | Satisfied by executable validation and tests |
| SemanticGraph validated | Satisfied by construction and GraphIR round trip |
| SemanticPlan integration validated | Satisfied for shortest-path requests |

Formal adoption remains conditional because:

1. `Custom(...)` relations are not supported by the closed `RelationType` enum.
2. Dedicated multi-trajectory SemanticSimulation validation is not implemented.
3. SCV-2 and later temporal/causal/spatial/dependency constraints remain
   experimental.

## Conclusion

Reasoning Space is implemented as a validated semantic state-transition
environment rather than a knowledge or memory store. The implementation
supports graph validation, exploration, closure, planning requests, transition
representation, and Graph IR conversion while preserving SCV-1 invariants.
