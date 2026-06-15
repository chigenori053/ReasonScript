# KEV-1 Knowledge Emergence Validation Specification

## Document Information

- Specification: KEV-1 Knowledge Emergence Validation
- Version: 0.1-draft
- Target: ReasonScript Semantic Language v0.2
- Status: Experimental Validation
- Runtime mapping: `RuntimeReal`
- Prerequisites:
  - SemanticUnit
  - SemanticRelation
  - SCV-1
  - Reasoning Space
  - SemanticPlan
  - SemanticSimulation
  - SimulationResult

## Purpose

KEV-1 validates that a successful structured reasoning result can be promoted
into an explicit, deterministic, and traceable `Knowledge` object.

Knowledge is not created merely because a state or relation exists in a graph.
It emerges only from a validated `SimulationResult`.

## Formal Definition

```text
Knowledge = Validated Structured Reasoning Result
```

Knowledge is not a raw state, raw relation, raw graph, simulation request,
knowledge repository, or truth assertion.

## Emergence Model

```text
Reasoning Space
      |
SemanticPlan
      |
SemanticSimulation
      |
SimulationResult
      |
KnowledgeGenerator
      |
Knowledge
```

## Runtime Types

| KEV-1 concept | RuntimeReal |
| --- | --- |
| Knowledge | `knowledge::Knowledge` |
| Emergent relation | `knowledge::SemanticRelation` |
| Evidence | `knowledge::KnowledgeEvidence` |
| Generator | `knowledge::KnowledgeGenerator` |
| Validator | `knowledge::KnowledgeValidator` |
| Error | `knowledge::KnowledgeError` |

## Knowledge Structure

```rust
pub struct Knowledge {
    pub relation: SemanticRelation,
    pub evidence: KnowledgeEvidence,
    pub confidence: f64,
}

pub struct SemanticRelation {
    pub source: Uuid,
    pub target: Uuid,
    pub relation: RelationType,
}

pub struct KnowledgeEvidence {
    pub source_plan: SemanticPlan,
    pub simulation_result: SimulationResult,
}
```

Knowledge has no generated identifier in KEV-1. Its value is derived entirely
from deterministic input, so repeated generation produces equal objects and
equal JSON.

## Simulation Evidence

`SimulationResult` records:

- the source `SemanticPlan`
- the selected path
- each transition
- source and target semantic unit types for each transition
- cost and confidence
- complete trace
- predicted states

The semantic unit types allow KEV-1 to enforce SCV-1 again at the knowledge
boundary without mutable access to the original Reasoning Space.

## Generation API

```rust
KnowledgeGenerator::new().generate(&simulation_result)
```

Output:

```rust
Result<Knowledge, KnowledgeError>
```

An unsuccessful or invalid simulation produces an error and no `Knowledge`.

## Generation Rules

1. `SimulationResult.success` must be `true`.
2. `distance` must be greater than zero.
3. Path length, distance, trace states, and trace steps must agree.
4. Source plan endpoints and constraints must agree with the path.
5. Predicted states must agree with the selected trajectory.
6. Trace cost and confidence must reproduce result cost and confidence.
7. Every trace transition must satisfy SCV-1.
8. The emergent endpoint relation must satisfy SCV-1.
9. Every transition in the trajectory must use the same relation type.
10. Knowledge confidence equals simulation confidence.

## Supported Relations

KEV-1 supports closure-compatible homogeneous trajectories:

- `IsA`
- `PartOf`
- `Cause`

KEV-1 rejects:

- `Similar`
- `Temporal`
- `Spatial`
- `Dependency`
- `Constraint`
- any future custom relation unless a later specification adopts it

## Metric Reproducibility

SSV-1 normalizes aggregated cost and confidence to 12 decimal places. KEV-1
recomputes those metrics from the trace using the same rule before promoting a
result. This prevents tampered or floating-point-drifted evidence from becoming
Knowledge.

## Validation Cases

| ID | Case | Expected |
| --- | --- | --- |
| KEV-001 | `Dog IsA Mammal IsA Animal` | `Dog IsA Animal` |
| KEV-002 | `Wheel PartOf Car PartOf Vehicle` | `Wheel PartOf Vehicle` |
| KEV-003 | `Collision Cause Damage Cause InsuranceClaim` | `Collision Cause InsuranceClaim` |
| KEV-004 | Unreachable goal | No Knowledge |
| KEV-005 | Evidence preservation | Plan, result, trace, confidence preserved |
| KEV-006 | Generate 100 times | Equal Knowledge and JSON |
| KEV-007 | JSON round trip | Knowledge unchanged |

Additional boundary validation rejects unsupported relations and endpoint
relations that violate SCV-1 even when each individual step is SCV-compatible.

## Non-Goals

- Truth validation
- Human or real-world correctness
- External fact validation
- Ontology correctness
- Persistent storage
- Knowledge repositories
- Knowledge retrieval
- Re-reasoning over Knowledge

## Adoption Criteria

KEV-1 can be adopted when:

1. KEV-001 through KEV-007 pass.
2. Knowledge generation is deterministic.
3. Complete evidence is preserved.
4. Confidence is preserved and reproducible.
5. JSON round trips without change.
6. SCV-1 is enforced at the knowledge boundary.
