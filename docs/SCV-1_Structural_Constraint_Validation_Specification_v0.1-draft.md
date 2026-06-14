# SCV-1 Structural Constraint Validation Specification

## Document Information

- Specification: SCV-1 Structural Constraint Validation
- Version: 0.1-draft
- Target: ReasonScript Semantic Language v0.2
- Status: Experimental Validation
- Runtime mapping: `RuntimeReal`

## Purpose

SCV-1 validates the structural integrity of semantic graphs. It detects invalid
semantic unit connections, invalid semantic relations, and structurally invalid
inference inputs.

SCV-1 does not prove that an inference result is true. It validates only the
typed structure of a `ReasonGraph`, which is the current `SemanticGraph`
representation in `RuntimeReal`.

## Runtime Type Mapping

| SCV-1 term | RuntimeReal type |
| --- | --- |
| `SemanticUnit` | `State` referenced by a `Node` |
| `SemanticUnitType` | `StateType` |
| `SemanticRelation` | `Edge` |
| `SemanticGraph` | `ReasonGraph` |
| Plan/execution entry | `Executor::infer` |

The public alias `SemanticUnitType = StateType` is provided by the structural
constraint module.

Supported SCV-1 unit types:

- `Concept`
- `Object`
- `Event`
- `Action`
- `Attribute`
- `Goal`
- `Constraint`

`Unknown` is not a valid SCV-1 semantic unit type.

## Validation Matrix

| Relation | Source | Target |
| --- | --- | --- |
| `IsA` | `Concept` | `Concept` |
| `IsA` | `Object` | `Concept` |
| `PartOf` | `Object` | `Object` |
| `PartOf` | `Object` | `Concept` |
| `Cause` | `Event` | `Event` |
| `Cause` | `Action` | `Event` |
| `Cause` | `Event` | `Attribute` |
| `Similar` | Any SCV-1 type | Same type |
| `Constraint` | `Constraint` | `Goal` |
| `Constraint` | `Constraint` | `Action` |
| `Constraint` | `Constraint` | `Event` |

`Temporal`, `Spatial`, and `Dependency` remain outside SCV-1 and are passed
through for validation by later specifications.

## Graph Validation Rules

1. Every edge has a source, relation, and target. This is enforced by the Rust
   `Edge` type.
2. Every edge source and target references an existing node.
3. Every node references an existing state with an SCV-1 semantic unit type.
4. Every relation is a defined `RelationType`. Unknown serialized relation
   names are rejected during deserialization.
5. Every SCV-1 relation satisfies the validation matrix.

## Validation API

```rust
StructuralConstraintValidator::validate_graph(
    graph: &ReasonGraph,
) -> Result<(), StructuralConstraintError>
```

The matrix predicate is also shared with the existing type checker:

```rust
StructuralConstraintValidator::is_compatible(source, relation, target)
```

This prevents the static type checker and semantic validator from maintaining
different relation rules.

## Execution Integration

`SemanticValidator::validate_graph` runs SCV-1 before context or knowledge
validation. Structural failures are mapped to:

```rust
SemanticError::InvalidStructure(String)
```

`Executor::infer` invokes semantic structural validation before type checking
or graph dynamics. Invalid graphs therefore cannot activate nodes, generate
closure edges, or mutate the execution timestamp.

`RuntimeReal` does not currently define a separate `SemanticPlan` generator.
For this runtime, the required pre-plan validation boundary is implemented at
the current higher-level execution entry point, `Executor::infer`.

## Conformance Tests

The canonical suite is:

`RuntimeReal/tests/scv_1_structural_constraint_validation.rs`

It contains SCV-001 through SCV-007 plus checks for same-type `Similar`,
missing state references, and execution-entry integration.

## Non-Goals

- Temporal constraint validation
- Causal truth or causal-cycle validation
- Spatial constraint validation
- Dependency constraint validation
- Knowledge correctness
- Simulation-result correctness
