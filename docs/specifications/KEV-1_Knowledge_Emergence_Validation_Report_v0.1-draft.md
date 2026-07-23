# KEV-1 Knowledge Emergence Validation Report

## Summary

- Date: 2026-06-15
- Specification: KEV-1 v0.1-draft
- Target: ReasonScript Semantic Language v0.2
- Runtime: `RuntimeReal`
- Result: PASS for KEV-1 draft scope

## Implemented Layer

Added `RuntimeReal/src/knowledge/`:

```text
knowledge/
├─ knowledge.rs
├─ evidence.rs
├─ generator.rs
├─ validator.rs
└─ mod.rs
```

The public API includes:

- `Knowledge`
- `SemanticRelation`
- `KnowledgeEvidence`
- `KnowledgeGenerator`
- `KnowledgeValidator`
- `KnowledgeError`
- `KNOWLEDGE_VERSION`

## SSV Evidence Extension

`SimulationResult` now retains its source `SemanticPlan`.

`SimulationStep` now retains source and target semantic unit types. This lets
KEV-1 independently verify both individual transitions and the emergent
endpoint relation against SCV-1.

Aggregated simulation metrics are normalized to 12 decimal places. This fixed
a detected one-ULP JSON round-trip difference for multiplied confidence values.

## Generation Behavior

`KnowledgeGenerator::generate(&SimulationResult)`:

1. validates the complete result and evidence,
2. rejects failed or zero-distance simulations,
3. requires one homogeneous closure-compatible relation,
4. verifies trace and plan consistency,
5. recomputes cost and confidence,
6. reapplies SCV-1,
7. constructs the endpoint relation,
8. preserves the source plan and complete simulation result.

Knowledge confidence is copied from the validated simulation confidence.

## Validation Results

| ID | Case | Result |
| --- | --- | --- |
| KEV-001 | Taxonomic emergence | PASS |
| KEV-002 | Part-whole emergence | PASS |
| KEV-003 | Causal emergence | PASS |
| KEV-004 | Failed simulation generates no Knowledge | PASS |
| KEV-005 | Plan, result, trace, and confidence are preserved | PASS |
| KEV-006 | 100 repeated generations are identical | PASS |
| KEV-007 | Knowledge JSON round trip is unchanged | PASS |

Additional validation:

- `Temporal` and other unsupported relations are rejected.
- A composed `Action Cause Attribute` relation is rejected even though its
  individual `Action Cause Event` and `Event Cause Attribute` steps are each
  SCV-1-compatible.
- Simulation metric and evidence inconsistencies are rejected.

Dedicated KEV result: 11 passed, 0 failed.

Regression command:

```text
cargo test -- --skip vs2_scaling_benchmarks
```

Regression result:

- 85 tests passed
- 0 tests failed
- 1 pre-existing scaling benchmark filtered out
- Documentation tests passed

## Design Decisions

### No generated Knowledge ID

A random UUID would make repeated generation unequal. KEV-1 models Knowledge
as a value derived from relation, evidence, and confidence. Persistence layers
may assign repository identifiers later without changing semantic identity.

### Homogeneous relation chains

KEV-1 generates one endpoint relation only when all simulation steps use the
same supported relation. Mixed-relation derivation requires explicit inference
rules and is outside this draft.

### Failure is not Knowledge

An unreachable goal remains a valid SSV result, but KEV-1 returns
`KnowledgeError::SimulationFailed`. No partial or negative Knowledge object is
created.

### Evidence is embedded

Knowledge contains both the source plan and complete simulation result. It can
therefore be audited without consulting mutable graph state or external
storage.

## Adoption Criteria

| Criterion | Status |
| --- | --- |
| KEV-001 through KEV-007 pass | Met |
| Deterministic Knowledge | Met; repeated 100 times |
| Evidence preserved | Met |
| Confidence preserved | Met |
| JSON round trip | Met |
| SCV-1 compatibility | Met at step and endpoint levels |

## Limitations

1. KEV-1 supports only homogeneous `IsA`, `PartOf`, and `Cause` trajectories.
2. Knowledge is an in-memory semantic value, not a repository record.
3. Truth, ontology correctness, temporal causality, and spatial causality
   remain outside the validation scope.
4. Knowledge use, accumulation, retrieval, and re-reasoning require later
   specifications.

## Conclusion

KEV-1 establishes the first formal `Knowledge` model in ReasonScript:

```text
Knowledge = Validated Structured Reasoning Result
```

The complete validated core pipeline is now:

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
