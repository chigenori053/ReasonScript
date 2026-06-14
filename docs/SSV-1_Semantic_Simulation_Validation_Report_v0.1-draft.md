# SSV-1 Semantic Simulation Validation Report

## Summary

- Date: 2026-06-15
- Specification: SSV-1 v0.1-draft
- Target: ReasonScript Semantic Language v0.2
- Runtime: `RuntimeReal`
- Result: PASS for SSV-1 draft scope

## Implemented Layer

Added the independent `semantic_simulation` module with:

- `SemanticSimulation`
- `SemanticSimulationError`
- `SimulationResult`
- `SimulationTrace`
- `SimulationStep`
- `SEMANTIC_SIMULATION_VERSION`

The layer borrows a `ReasoningSpace` immutably. It evaluates trajectories but
does not execute graph dynamics, create closure relations, write storage, or
produce knowledge.

## Plan Integration

`SemanticPlan` now includes defaulted optional constraints:

- nodes that must be avoided
- maximum path distance

Existing `SemanticPlan::new(start, goal)` callers remain compatible and receive
an unconstrained plan.

## Cost and Confidence

The existing `Edge::cost` field had previously also been described as
confidence in part of the runtime. SSV-1 separates these concepts by adding an
independent, backward-compatible `Edge::confidence` field.

Simulation computes:

```text
cost       = sum(path edge costs)
confidence = product(path edge confidences)
```

Negative or non-finite costs and confidence values outside `[0.0, 1.0]` are
rejected. Closure-generated edges now compose both metrics correctly.

## Validation Results

| ID | Case | Result |
| --- | --- | --- |
| SSV-001 | Reachable `Dog -> Mammal -> Animal` goal | PASS |
| SSV-002 | Unreachable goal returns `success=false` | PASS |
| SSV-003 | Repeated result, JSON, cost, and confidence are identical | PASS |
| SSV-004 | SCV-invalid graph is rejected at simulation boundary | PASS |
| SSV-005 | State trace equals path; transition trace equals distance | PASS |
| SSV-006 | Future semantic states are predicted | PASS |
| SSV-007 | Reasoning Space is byte-for-byte JSON-equivalent after simulation | PASS |

Additional validation:

- Plan avoidance constraints are enforced.
- Invalid confidence is rejected.
- `SimulationResult` JSON round trips without loss.

Dedicated SSV result: 9 passed, 0 failed.

Regression command:

```text
cargo test -- --skip vs2_scaling_benchmarks
```

Regression result:

- 74 tests passed
- 0 tests failed
- 1 pre-existing scaling benchmark filtered out
- Documentation tests passed

The excluded benchmark performs debug-mode closure over 100, 500, and
1000-node graphs. All normal closure, SCV-1, Reasoning Space, executor, IR, and
simulation tests passed.

## Behavioral Decisions

### Unreachable is a result

An existing but unreachable goal is a valid simulation outcome rather than a
runtime failure. It returns a structured unsuccessful result. Missing nodes and
invalid structural input remain errors.

### Trace completeness

The specification requires `trace length = path length`. RuntimeReal represents
this explicitly as:

- `trace.states.len() == path.len()`
- `trace.steps.len() == distance`

This records both every visited semantic state and every simulated transition.

### Prediction

The standalone `predict` operation returns all directed states reachable from
the current state. A successful simulation result contains the future states
on the selected trajectory. An unsuccessful result retains the states that are
still reachable from the start.

## Adoption Criteria

| Criterion | Status |
| --- | --- |
| All SSV cases pass | Met |
| Deterministic simulation | Met; repeated 100 times |
| SCV-1 enforcement | Met |
| Immutable Reasoning Space | Met |
| Reproducible SimulationResult | Met through equality and JSON round trip |

## Limitations

1. Path selection optimizes hop count, not total cost. Cost is evaluated after
   selecting the deterministic shortest-hop path.
2. Confidence is an input metric; SSV-1 does not establish its real-world
   calibration.
3. Temporal and spatial causal correctness remain outside SSV-1.
4. SSV-1 produces no `Knowledge` object. That transformation belongs to a
   future KEV-1 phase.

## Conclusion

SSV-1 establishes Semantic Simulation as an independent validated layer above
Reasoning Space and SemanticPlan. It produces deterministic, structured,
serializable trajectory results while preserving SCV-1 and leaving the
Reasoning Space unchanged.
