# SCV-1 Structural Constraint Validation Report

## Result

- Date: 2026-06-15
- Target crate: `RuntimeReal`
- Specification: SCV-1 v0.1-draft
- Adoption status: ADOPTED by ReasonScript Semantic Language v0.2 Core
- Overall result: PASS

## Implemented Components

### Structural validator

Added `core::structural_constraint` with:

- `SemanticUnitType`
- `StructuralConstraintValidator`
- `StructuralConstraintError`
- The complete SCV-1 initial validation matrix
- Node-to-state and edge-to-node referential validation
- Rejection of `StateType::Unknown`

### Error integration

Added `SemanticError::InvalidStructure(String)`.

`SemanticValidator::validate_graph` now runs SCV-1 first and converts structural
validation failures into `InvalidStructure`.

### Execution integration

`Executor::infer` now validates semantic structure before runtime type checking
and dynamics. The integration test confirms that a rejected graph leaves the
execution timestamp and active-node set unchanged.

### Type-system consistency

`TypeChecker::is_compatible` now delegates to the SCV-1 matrix. This removed
the previous conflicts:

- `Object IsA Concept` was previously rejected.
- `Event IsA Event` was previously accepted.
- `Similar` previously accepted different types.
- `Constraint` previously used the reverse source/target direction.

## SCV Test Results

| ID | Case | Expected | Result |
| --- | --- | --- | --- |
| SCV-001 | `Concept IsA Concept` | PASS | PASS |
| SCV-002 | `Object IsA Concept` | PASS | PASS |
| SCV-003 | `Event IsA Object` | FAIL | PASS |
| SCV-004 | `Goal PartOf Attribute` | FAIL | PASS |
| SCV-005 | `Constraint Constraint Action` | PASS | PASS |
| SCV-006 | Missing source node | FAIL | PASS |
| SCV-007 | Undefined serialized relation | FAIL | PASS |

Additional tests:

- `Similar` rejects different semantic unit types.
- Every node must reference an existing state.
- `SemanticValidator` reports `InvalidStructure`.
- `Executor::infer` rejects invalid structure before execution.

SCV suite result: 11 passed, 0 failed.

## Regression Results

Command:

```text
cargo test -- --skip vs2_scaling_benchmarks
```

Result:

- 93 tests passed
- 0 tests failed
- 1 test filtered out
- Documentation tests passed

The excluded `vs2_scaling_benchmarks` test performs transitive closure at 100,
500, and 1000 nodes. A full debug-mode run was attempted and manually stopped
after several minutes during that pre-existing benchmark. All other tests,
including the mixed semantic closure benchmark, passed.

Existing compiler warnings remain in unrelated files. No new warning is
introduced by the SCV-1 module or test suite.

## Adoption Criteria

| Criterion | Status | Evidence |
| --- | --- | --- |
| All SCV tests pass | Met | 11/11 SCV tests passed |
| SemanticPlan consistency | Met | `ReasoningSpace::execute_plan` and `SemanticSimulation` apply SCV-1 before trajectory evaluation |
| SemanticSimulation compatibility | Met | SSV-1 and the Semantic Language v0.2 Core gate pass |
| Reason IR conversion possible | Met for current graph IR | `GraphIR` wraps the serializable `ReasonGraph`; relation names are enum-validated during deserialization |

## Limitations

1. `Edge` is strongly typed, so missing source/relation/target fields and
   undefined relation names fail during Rust construction or Serde
   deserialization rather than inside `validate_graph`.
2. SCV-1 intentionally does not validate `Temporal`, `Spatial`, or `Dependency`
   relation matrices.
3. The scaling benchmark should be moved to an ignored or release-mode
   performance suite so ordinary regression runs complete predictably.

## Conclusion

SCV-1 is adopted as the executable structural type system for ReasonScript
Semantic Language v0.2 Core. Invalid semantic topology is rejected before
reasoning, simulation, or Knowledge emergence.
